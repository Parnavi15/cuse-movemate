"""
Telling students what just happened.

Every notification is written in the same transaction as the state change that
caused it, so a notification can't describe something that didn't happen.

Two channels:
  - In app, always. The bell in the nav polls for these.
  - Email, only for the two events a student would want pulled out of the app:
    somebody wants their item, and their request was accepted. Everything else
    would be noise, and noisy apps get muted.
"""
import logging

from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from .models import Notification

log = logging.getLogger(__name__)

# The only kinds worth an email. Keep this list short on purpose.
EMAIL_KINDS = {"request_received", "request_accepted"}

EMAIL_HTML = """\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:24px;background:#F4F3F1;
               font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#22262A;">
    <div style="max-width:480px;margin:0 auto;background:#fff;
                border:1px solid #E4E1DD;border-radius:14px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#F76900,#E1590A 55%,#B8460A);
                  color:#fff;padding:20px 24px;font-size:19px;font-weight:800;">
        &#9851; Cuse-MoveMate
      </div>
      <div style="padding:24px;">
        <h2 style="margin:0 0 10px;font-size:20px;">{title}</h2>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.55;">{body}</p>
        <a href="{url}" style="display:inline-block;background:#E1590A;color:#fff;
                  text-decoration:none;padding:11px 20px;border-radius:9px;
                  font-weight:700;font-size:15px;">{cta}</a>
      </div>
      <div style="padding:14px 24px;border-top:1px solid #E4E1DD;
                  font-size:13px;color:#757D84;">
        Turn these off any time in your profile.
      </div>
    </div>
  </body>
</html>
"""

CTA = {
    "request_received": "Review the request",
    "request_accepted": "Arrange pickup",
}


def _send_email(notification):
    user = notification.user
    address = user.campus_email or user.email
    if not address or not user.email_notifications:
        return False

    base = getattr(settings, "APP_BASE_URL", "http://localhost:5173")
    url = f"{base}{notification.link}"
    try:
        message = EmailMultiAlternatives(
            subject=f"Cuse-MoveMate: {notification.title}",
            body=f"{notification.title}\n\n{notification.body}\n\n{url}\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[address],
        )
        message.attach_alternative(
            EMAIL_HTML.format(
                title=notification.title,
                body=notification.body,
                url=url,
                cta=CTA.get(notification.kind, "Open Cuse-MoveMate"),
            ),
            "text/html",
        )
        message.send(fail_silently=False)
        return True
    except Exception:
        # A failed email must never roll back the thing it was describing.
        log.exception("Notification email to %s failed", address)
        return False


def notify(user, kind, title, body="", link="/requests", txn=None, actor=None):
    """Write one notification, and email it if the kind warrants it."""
    if actor is not None and actor.id == user.id:
        return None  # nobody needs to be told about their own tap

    notification = Notification.objects.create(
        user=user, kind=kind, title=title, body=body,
        link=link, transaction=txn, actor=actor,
    )
    if kind in EMAIL_KINDS:
        if _send_email(notification):
            notification.emailed = True
            notification.save(update_fields=["emailed"])
    return notification


# --------------------------------------------------------------------------
# Event helpers. Each one knows who cares and what they'd want to read.
# --------------------------------------------------------------------------

def _price(txn):
    if txn.mode == "free":
        return "for free"
    if txn.mode == "trade":
        return "as a trade"
    return f"for ${txn.price_cents / 100:.2f}"


def request_received(txn):
    """A buyer claimed a seller's listing."""
    notify(
        txn.owner,
        "request_received",
        f"{txn.claimant.username} wants your {txn.listing.title}",
        (txn.message or f"They'd like to take it {_price(txn)}.")[:300],
        link="/requests",
        txn=txn,
        actor=txn.claimant,
    )


def request_accepted(txn):
    notify(
        txn.claimant,
        "request_accepted",
        f"{txn.owner.username} accepted — {txn.listing.title} is yours",
        (txn.pickup_note or f"Message them to arrange pickup in {txn.listing.address_label}."),
        link="/requests",
        txn=txn,
        actor=txn.owner,
    )


def request_rejected(txn):
    notify(
        txn.claimant,
        "request_rejected",
        f"{txn.listing.title} went to someone else",
        "Try the smart match — students list new things every day.",
        link="/match",
        txn=txn,
        actor=txn.owner,
    )


def handoff_pending(txn, confirmed_by):
    other = txn.other_party(confirmed_by)
    notify(
        other,
        "handoff_pending",
        f"{confirmed_by.username} confirmed the handoff",
        "Your tap completes it and releases the points for both of you.",
        link="/requests",
        txn=txn,
        actor=confirmed_by,
    )


def handoff_complete(txn):
    for user in (txn.owner, txn.claimant):
        notify(
            user,
            "handoff_complete",
            f"{txn.listing.title} is now in circulation",
            "Points are pending for 24 hours, then they post. Leave a review for 5 more.",
            link="/wallet",
            txn=txn,
        )


def review_received(review):
    notify(
        review.subject,
        "review_received",
        f"{review.author.username} left you {review.stars} stars",
        (review.body or "")[:300],
        link="/requests",
        txn=review.transaction,
        actor=review.author,
    )


def _when(dt):
    return dt.strftime("%a %-d %b, %-I:%M %p")


def time_proposed(txn, by):
    other = txn.other_party(by)
    notify(
        other,
        "time_proposed",
        f"{by.username} suggested {_when(txn.pickup_at)}",
        f"For {txn.listing.title} at {txn.listing.address_label}. Agree or suggest another time.",
        link="/requests",
        txn=txn,
        actor=by,
    )


def time_agreed(txn, by):
    other = txn.other_party(by)
    notify(
        other,
        "time_agreed",
        f"Pickup set for {_when(txn.pickup_at)}",
        f"{by.username} agreed. {txn.listing.title} at {txn.listing.address_label}.",
        link="/requests",
        txn=txn,
        actor=by,
    )


def badge_earned(user, badge):
    notify(
        user,
        "badge_earned",
        f"{badge.icon} {badge.name} unlocked",
        f"{badge.description} — worth {badge.bonus_points} points.",
        link="/wallet",
    )
