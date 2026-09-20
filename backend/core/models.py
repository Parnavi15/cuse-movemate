from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

# Syracuse University Quad, used as the default campus centre.
CAMPUS_LAT = 43.0392
CAMPUS_LNG = -76.1351


class User(AbstractUser):
    """A student. Anyone can browse and earn; only a verified student can redeem."""

    campus_email = models.EmailField(blank=True, default="")
    is_verified_student = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, default="")
    verification_sent_at = models.DateTimeField(null=True, blank=True)

    school = models.CharField(max_length=120, default="Syracuse University")
    avatar_emoji = models.CharField(max_length=8, default="🧑‍🎓")
    bio = models.CharField(max_length=240, blank=True, default="")

    latitude = models.FloatField(default=CAMPUS_LAT)
    longitude = models.FloatField(default=CAMPUS_LNG)
    address_label = models.CharField(max_length=120, default="Near campus")

    rating_avg = models.FloatField(default=0.0)
    rating_count = models.PositiveIntegerField(default=0)

    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return self.username

    def recompute_rating(self):
        agg = Review.objects.filter(subject=self).aggregate(
            n=models.Count("id"), avg=models.Avg("stars")
        )
        self.rating_count = agg["n"] or 0
        self.rating_avg = round(agg["avg"] or 0.0, 2)
        self.save(update_fields=["rating_count", "rating_avg"])


class Category(models.Model):
    """Impact constants live here, not in code, so a sustainability office can edit them."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    icon = models.CharField(max_length=8, default="📦")
    avg_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, default=2)
    co2e_kg = models.DecimalField(max_digits=6, decimal_places=2, default=5)
    est_value_cents = models.IntegerField(default=1500)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Listing(models.Model):
    MODE = [("free", "Free"), ("sale", "For sale"), ("trade", "Trade")]
    CONDITION = [
        ("new", "Like new"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("worn", "Well used"),
    ]
    STATUS = [
        ("active", "Active"),
        ("reserved", "Reserved"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    owner = models.ForeignKey(User, related_name="listings", on_delete=models.CASCADE)
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True, default="")
    category = models.ForeignKey(Category, related_name="listings", on_delete=models.PROTECT)
    mode = models.CharField(max_length=8, choices=MODE, default="free")
    price_cents = models.IntegerField(default=0)
    trade_for = models.CharField(max_length=140, blank=True, default="")
    condition = models.CharField(max_length=8, choices=CONDITION, default="good")
    photo_url = models.URLField(blank=True, default="")

    latitude = models.FloatField(default=CAMPUS_LAT)
    longitude = models.FloatField(default=CAMPUS_LNG)
    address_label = models.CharField(max_length=120, default="Near campus")

    pickup_deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="active")
    views = models.PositiveIntegerField(default=0)
    ownership_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.mode})"

    @property
    def price_display(self):
        if self.mode == "free":
            return "Free"
        if self.mode == "trade":
            return f"Trade for {self.trade_for or 'anything useful'}"
        return f"${self.price_cents / 100:.2f}"

    @property
    def is_point_eligible(self):
        """Quality gate. A listing has to be real enough to be worth rewarding."""
        return bool(self.photo_url) and bool(self.pickup_deadline) and bool(self.description)


class Transaction(models.Model):
    """requested -> accepted -> completed -> reviewed, with reject/cancel/dispute exits."""

    STATES = [
        ("requested", "Requested"),
        ("accepted", "Accepted"),
        ("completed", "Completed"),
        ("reviewed", "Reviewed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("disputed", "Disputed"),
    ]

    listing = models.ForeignKey(Listing, related_name="transactions", on_delete=models.PROTECT)
    owner = models.ForeignKey(User, related_name="sales", on_delete=models.PROTECT)
    claimant = models.ForeignKey(User, related_name="claims", on_delete=models.PROTECT)
    mode = models.CharField(max_length=8, choices=Listing.MODE)
    state = models.CharField(max_length=12, choices=STATES, default="requested")

    message = models.CharField(max_length=300, blank=True, default="")
    pickup_note = models.CharField(max_length=200, blank=True, default="")

    price_cents = models.IntegerField(default=0)
    credit_applied_cents = models.IntegerField(default=0)

    # Agreeing a time is its own small handshake: one side proposes, the other
    # agrees. Storing both halves means the card can always say whose move it is.
    pickup_at = models.DateTimeField(null=True, blank=True)
    pickup_proposed_by = models.ForeignKey(
        User, null=True, blank=True, related_name="+", on_delete=models.SET_NULL
    )
    pickup_agreed_at = models.DateTimeField(null=True, blank=True)

    owner_confirmed_at = models.DateTimeField(null=True, blank=True)
    claimant_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.listing.title}: {self.owner} -> {self.claimant} [{self.state}]"

    @property
    def amount_due_cents(self):
        return max(0, self.price_cents - self.credit_applied_cents)

    def other_party(self, user):
        return self.claimant if user == self.owner else self.owner


class Review(models.Model):
    transaction = models.ForeignKey(Transaction, related_name="reviews", on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name="reviews_written", on_delete=models.CASCADE)
    subject = models.ForeignKey(User, related_name="reviews_received", on_delete=models.CASCADE)
    stars = models.PositiveSmallIntegerField()
    on_time = models.BooleanField(default=True)
    easy_to_reach = models.BooleanField(default=True)
    would_repeat = models.BooleanField(default=True)
    body = models.CharField(max_length=400, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(fields=["transaction", "author"], name="one_review_per_side")
        ]


class Message(models.Model):
    """
    Chat scoped to one transaction.

    Not a general inbox: a conversation only exists because two students are
    arranging a specific handoff, and it disappears from view when that handoff
    is done. That scoping is also what makes moderation tractable — every
    message has a transaction attached to it.
    """

    transaction = models.ForeignKey(
        Transaction, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(User, related_name="messages_sent", on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["transaction", "created_at"])]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"


class Wallet(models.Model):
    """Balances are a cached sum of the ledger. Never edit them by hand."""

    user = models.OneToOneField(User, related_name="wallet", on_delete=models.CASCADE)
    points_posted = models.IntegerField(default=0)
    points_pending = models.IntegerField(default=0)
    credit_cents = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.points_posted} pts"


class PointEntry(models.Model):
    """Append-only ledger. Every point in a balance traces back to one of these rows."""

    RULES = [
        ("give_away", "Gave an item away"),
        ("trade", "Completed a trade"),
        ("reused", "Item kept in circulation"),
        ("sale", "Sold an item"),
        ("claim", "Claimed an item"),
        ("bulk_list", "Listed 3+ move-out items"),
        ("review", "Left a review"),
        ("verify", "Verified student email"),
        ("badge", "Badge bonus"),
        ("redeem", "Redeemed for credit"),
    ]
    STATUS = [("pending", "Pending"), ("posted", "Posted"), ("reversed", "Reversed")]

    wallet = models.ForeignKey(Wallet, related_name="entries", on_delete=models.CASCADE)
    rule = models.CharField(max_length=16, choices=RULES)
    points = models.IntegerField()
    status = models.CharField(max_length=8, choices=STATUS, default="pending")
    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, related_name="point_entries", on_delete=models.SET_NULL
    )
    note = models.CharField(max_length=160, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    posts_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A double-tapped confirm button cannot mint points twice.
            UniqueConstraint(
                fields=["wallet", "rule", "transaction"],
                name="one_award_per_rule_per_txn",
                condition=models.Q(transaction__isnull=False),
            )
        ]


class Redemption(models.Model):
    wallet = models.ForeignKey(Wallet, related_name="redemptions", on_delete=models.CASCADE)
    points_spent = models.IntegerField()
    credit_cents = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class Badge(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    icon = models.CharField(max_length=8, default="🏅")
    description = models.CharField(max_length=160)
    threshold = models.IntegerField(default=1)
    metric = models.CharField(max_length=24, default="completed")  # completed | given | reviews
    bonus_points = models.IntegerField(default=0)

    class Meta:
        ordering = ["threshold"]

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(User, related_name="badges", on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [UniqueConstraint(fields=["user", "badge"], name="one_badge_per_user")]


class Notification(models.Model):
    """
    One row per thing a student should know about.

    Written by core/notify.py at the same moment the state change happens, so
    a notification can never describe something that didn't occur.
    """

    KINDS = [
        ("request_received", "Someone wants your item"),
        ("request_accepted", "Your request was accepted"),
        ("request_rejected", "Your request was declined"),
        ("handoff_pending", "Waiting on your confirmation"),
        ("handoff_complete", "Handoff confirmed"),
        ("review_received", "You got a review"),
        ("points_posted", "Points posted"),
        ("badge_earned", "Badge earned"),
        ("item_claimed", "Your item was claimed"),
        ("message", "New message"),
        ("time_proposed", "Pickup time proposed"),
        ("time_agreed", "Pickup time agreed"),
    ]

    user = models.ForeignKey(User, related_name="notifications", on_delete=models.CASCADE)
    kind = models.CharField(max_length=24, choices=KINDS)
    title = models.CharField(max_length=140)
    body = models.CharField(max_length=300, blank=True, default="")
    link = models.CharField(max_length=120, default="/requests")
    transaction = models.ForeignKey(
        "Transaction", null=True, blank=True, related_name="notifications",
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        User, null=True, blank=True, related_name="notifications_caused",
        on_delete=models.SET_NULL,
    )
    read_at = models.DateTimeField(null=True, blank=True)
    emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user}: {self.title}"


class NeedRequest(models.Model):
    """A saved 'what do I need?' query, so we can show a student their match history."""

    user = models.ForeignKey(User, related_name="needs", on_delete=models.CASCADE)
    raw_text = models.CharField(max_length=400)
    parsed = models.JSONField(default=dict)
    result_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
