"""
The MovePoints economy.

One rule holds the whole thing together: points are created by exactly one event,
both students confirming a handoff. Everything else in this file is a guardrail
around that event or a way to spend what it produced.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction as db_transaction
from django.utils import timezone

from .models import Badge, PointEntry, Redemption, Transaction, UserBadge, Wallet

# --------------------------------------------------------------------------
# Economy constants
# --------------------------------------------------------------------------

POINTS_PER_DOLLAR = 20          # 20 MovePoints = $1.00 of credit
REDEEM_BLOCK = 100              # redeem in 100-point ($5) blocks
MAX_CREDIT_SHARE = 0.5          # credit covers at most half an item's price
PENDING_HOURS = 24              # dispute window before points post
PAIR_LIMIT = 2                  # same two students, max 2 earning txns / 30 days
PAIR_WINDOW_DAYS = 30
WEEKLY_CEILING = 300            # points a single student can earn per 7 days

RULE_POINTS = {
    "give_away": 50,
    "trade": 30,
    "reused": 25,
    "sale": 20,
    "claim": 10,
    "bulk_list": 10,
    "review": 5,
    "verify": 25,
}

RULE_LABELS = dict(PointEntry.RULES)


def points_to_cents(points):
    return int(round(points / POINTS_PER_DOLLAR * 100))


def cents_to_points(cents):
    return int(round(cents / 100 * POINTS_PER_DOLLAR))


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


# --------------------------------------------------------------------------
# Guardrails
# --------------------------------------------------------------------------

def pair_transaction_count(owner, claimant):
    """How many point-earning transactions this pair has completed recently."""
    since = timezone.now() - timedelta(days=PAIR_WINDOW_DAYS)
    return Transaction.objects.filter(
        models.Q(owner=owner, claimant=claimant) | models.Q(owner=claimant, claimant=owner),
        state__in=["completed", "reviewed"],
        updated_at__gte=since,
    ).count()


def points_earned_this_week(user):
    since = timezone.now() - timedelta(days=7)
    agg = PointEntry.objects.filter(
        wallet__user=user,
        created_at__gte=since,
        status__in=["pending", "posted"],
        points__gt=0,
    ).aggregate(total=models.Sum("points"))
    return agg["total"] or 0


def earning_blocked_reason(user, txn=None):
    """Returns a human-readable reason, or None when the student may earn."""
    if txn is not None:
        if not txn.listing.is_point_eligible:
            return "Listing needs a photo, a description and a pickup deadline to earn points."
        if pair_transaction_count(txn.owner, txn.claimant) > PAIR_LIMIT:
            return (
                f"You and this student have already earned on {PAIR_LIMIT} handoffs "
                f"in the last {PAIR_WINDOW_DAYS} days."
            )
    if points_earned_this_week(user) >= WEEKLY_CEILING:
        return f"Weekly earning ceiling of {WEEKLY_CEILING} points reached."
    return None


# --------------------------------------------------------------------------
# Awarding
# --------------------------------------------------------------------------

def award(user, rule, txn=None, points=None, note=""):
    """Write one pending ledger row. Idempotent per (wallet, rule, transaction)."""
    wallet = get_wallet(user)
    amount = RULE_POINTS.get(rule, 0) if points is None else points
    if amount == 0:
        return None

    blocked = earning_blocked_reason(user, txn)
    if blocked and rule not in ("badge", "verify"):
        return None

    if txn is not None and PointEntry.objects.filter(
        wallet=wallet, rule=rule, transaction=txn
    ).exists():
        return None

    entry = PointEntry.objects.create(
        wallet=wallet,
        rule=rule,
        points=amount,
        status="pending",
        transaction=txn,
        note=note or RULE_LABELS.get(rule, rule),
        posts_at=timezone.now() + timedelta(hours=PENDING_HOURS),
    )
    recompute(wallet)
    return entry


@db_transaction.atomic
def award_for_handoff(txn):
    """Fires on exactly one state edge: accepted -> completed."""
    if txn.mode == "free":
        award(txn.owner, "give_away", txn, note=f"Gave away {txn.listing.title}")
    elif txn.mode == "trade":
        award(txn.owner, "trade", txn, note=f"Traded {txn.listing.title}")
        award(txn.claimant, "trade", txn, note=f"Traded for {txn.listing.title}")
    else:
        award(txn.owner, "sale", txn, note=f"Sold {txn.listing.title}")

    if txn.mode != "trade":
        award(txn.claimant, "claim", txn, note=f"Claimed {txn.listing.title}")

    # The circulation bonus goes to both sides of every completed handoff.
    award(txn.owner, "reused", txn, note="Item kept in circulation")
    award(txn.claimant, "reused", txn, note="Item kept in circulation")

    check_badges(txn.owner)
    check_badges(txn.claimant)


def award_bulk_listing_bonus(user):
    """+10 once a student's third point-eligible listing goes live in a 14-day window."""
    from .models import Listing

    since = timezone.now() - timedelta(days=14)
    live = [
        l for l in Listing.objects.filter(owner=user, created_at__gte=since, status="active")
        if l.is_point_eligible
    ]
    if len(live) < 3:
        return None
    already = PointEntry.objects.filter(
        wallet__user=user, rule="bulk_list", created_at__gte=since
    ).exists()
    if already:
        return None
    return award(user, "bulk_list", note="Listed 3+ move-out items")


def reverse_for_transaction(txn, reason="Transaction disputed"):
    """Pending points vanish. Posted points are clawed back as a negative row."""
    for entry in PointEntry.objects.filter(transaction=txn).exclude(status="reversed"):
        if entry.status == "pending":
            entry.status = "reversed"
            entry.save(update_fields=["status"])
        else:
            PointEntry.objects.create(
                wallet=entry.wallet,
                rule=entry.rule,
                points=-entry.points,
                status="posted",
                transaction=None,
                note=reason,
                posts_at=timezone.now(),
            )
            entry.status = "reversed"
            entry.save(update_fields=["status"])
        recompute(entry.wallet)


# --------------------------------------------------------------------------
# Settlement
# --------------------------------------------------------------------------

def settle(wallet=None, force=False):
    """
    Move pending entries past their dispute window into posted.

    In production this is an hourly Celery beat job. Here it also runs lazily on
    every wallet read, which keeps the demo honest without a worker process.
    """
    qs = PointEntry.objects.filter(status="pending")
    if wallet is not None:
        qs = qs.filter(wallet=wallet)
    if not force:
        qs = qs.filter(posts_at__lte=timezone.now())

    wallets = set()
    for entry in qs:
        entry.status = "posted"
        entry.posts_at = min(entry.posts_at, timezone.now())
        entry.save(update_fields=["status", "posts_at"])
        wallets.add(entry.wallet_id)

    for wid in wallets:
        recompute(Wallet.objects.get(pk=wid))
    return len(wallets)


def recompute(wallet):
    posted = wallet.entries.filter(status="posted").aggregate(s=models.Sum("points"))["s"] or 0
    pending = wallet.entries.filter(status="pending").aggregate(s=models.Sum("points"))["s"] or 0
    earned = (
        wallet.entries.filter(status="posted", points__gt=0).exclude(rule="redeem")
        .aggregate(s=models.Sum("points"))["s"] or 0
    )
    wallet.points_posted = posted
    wallet.points_pending = pending
    wallet.lifetime_points = earned
    wallet.save(update_fields=["points_posted", "points_pending", "lifetime_points", "updated_at"])
    return wallet


# --------------------------------------------------------------------------
# Redeeming
# --------------------------------------------------------------------------

class RedeemError(Exception):
    pass


@db_transaction.atomic
def redeem(user, points):
    wallet = get_wallet(user)
    settle(wallet)
    wallet.refresh_from_db()

    if not user.is_verified_student:
        raise RedeemError("Verify your .edu email before redeeming points.")
    if points <= 0 or points % REDEEM_BLOCK != 0:
        raise RedeemError(f"Redeem in blocks of {REDEEM_BLOCK} points.")
    if points > wallet.points_posted:
        raise RedeemError("Not enough posted points. Pending points can't be redeemed yet.")

    cents = points_to_cents(points)
    PointEntry.objects.create(
        wallet=wallet,
        rule="redeem",
        points=-points,
        status="posted",
        note=f"Redeemed for ${cents / 100:.2f} credit",
        posts_at=timezone.now(),
    )
    wallet.credit_cents += cents
    wallet.save(update_fields=["credit_cents"])
    Redemption.objects.create(wallet=wallet, points_spent=points, credit_cents=cents)
    recompute(wallet)
    return wallet


def max_credit_for(price_cents, wallet):
    """Credit never covers more than half a price, so the seller still gets paid."""
    return min(wallet.credit_cents, int(price_cents * MAX_CREDIT_SHARE))


@db_transaction.atomic
def spend_credit(user, cents):
    wallet = get_wallet(user)
    if cents <= 0:
        return 0
    if cents > wallet.credit_cents:
        raise RedeemError("Not enough wallet credit.")
    wallet.credit_cents -= cents
    wallet.save(update_fields=["credit_cents"])
    return cents


# --------------------------------------------------------------------------
# Badges
# --------------------------------------------------------------------------

def metric_value(user, metric):
    completed = Transaction.objects.filter(
        models.Q(owner=user) | models.Q(claimant=user), state__in=["completed", "reviewed"]
    )
    if metric == "completed":
        return completed.count()
    if metric == "given":
        return completed.filter(owner=user, mode="free").count()
    if metric == "reviews":
        return user.reviews_received.filter(stars__gte=4).count()
    return 0


def check_badges(user):
    earned = []
    have = set(UserBadge.objects.filter(user=user).values_list("badge__slug", flat=True))
    for badge in Badge.objects.all():
        if badge.slug in have:
            continue
        if metric_value(user, badge.metric) >= badge.threshold:
            UserBadge.objects.create(user=user, badge=badge)
            if badge.bonus_points:
                award(user, "badge", points=badge.bonus_points, note=f"{badge.name} badge")
            from . import notify as notifier

            notifier.badge_earned(user, badge)
            earned.append(badge)
    return earned


def badge_progress(user):
    have = set(UserBadge.objects.filter(user=user).values_list("badge__slug", flat=True))
    out = []
    for badge in Badge.objects.all():
        value = metric_value(user, badge.metric)
        out.append({
            "slug": badge.slug,
            "name": badge.name,
            "icon": badge.icon,
            "description": badge.description,
            "earned": badge.slug in have,
            "progress": min(value, badge.threshold),
            "threshold": badge.threshold,
            "bonus_points": badge.bonus_points,
        })
    return out


# --------------------------------------------------------------------------
# Impact Wallet
# --------------------------------------------------------------------------

def impact_for(user):
    """
    Every figure here is derived from completed transactions times per-category
    constants stored in the database. Nothing is invented at render time.
    """
    txns = Transaction.objects.filter(
        models.Q(owner=user) | models.Q(claimant=user), state__in=["completed", "reviewed"]
    ).select_related("listing__category")

    items = 0
    weight = Decimal("0")
    co2e = Decimal("0")
    saved_cents = 0

    for t in txns:
        cat = t.listing.category
        items += 1
        weight += cat.avg_weight_kg
        co2e += cat.co2e_kg
        if t.claimant_id == user.id:
            saved_cents += max(0, cat.est_value_cents - t.price_cents)

    wallet = get_wallet(user)
    return {
        "points_posted": wallet.points_posted,
        "points_pending": wallet.points_pending,
        "credit_cents": wallet.credit_cents,
        "lifetime_points": wallet.lifetime_points,
        "items_circulated": items,
        "weight_kg": float(round(weight, 1)),
        "co2e_kg": float(round(co2e, 1)),
        "savings_cents": saved_cents,
        "note": "Impact figures are estimates based on category averages.",
    }


def reward_table():
    """Shown in the UI so students know exactly what each action is worth."""
    return [
        {"rule": "give_away", "label": "Give an item away", "icon": "🎁", "points": RULE_POINTS["give_away"]},
        {"rule": "trade", "label": "Complete a trade", "icon": "🤝", "points": RULE_POINTS["trade"]},
        {"rule": "reused", "label": "Item kept in circulation", "icon": "♻️", "points": RULE_POINTS["reused"]},
        {"rule": "sale", "label": "Sell an item", "icon": "💵", "points": RULE_POINTS["sale"]},
        {"rule": "claim", "label": "Buy or claim an item", "icon": "🛍️", "points": RULE_POINTS["claim"]},
        {"rule": "bulk_list", "label": "List 3+ move-out items", "icon": "📦", "points": RULE_POINTS["bulk_list"]},
        {"rule": "review", "label": "Leave a useful review", "icon": "⭐", "points": RULE_POINTS["review"]},
        {"rule": "verify", "label": "Verify your .edu email", "icon": "🎓", "points": RULE_POINTS["verify"]},
    ]
