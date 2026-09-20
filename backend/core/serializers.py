from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import serializers

from . import campus, rewards
from .models import (Category, Listing, Message, NeedRequest, Notification,
                     PointEntry, Review, Transaction, Wallet)

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "avatar_emoji", "school", "is_verified_student",
                  "rating_avg", "rating_count", "address_label"]


class UserSerializer(serializers.ModelSerializer):
    wallet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "campus_email", "is_verified_student",
                  "school", "avatar_emoji", "bio", "latitude", "longitude",
                  "address_label", "rating_avg", "rating_count", "wallet",
                  "email_notifications", "activity"]
        read_only_fields = ["is_verified_student", "rating_avg", "rating_count"]

    activity = serializers.SerializerMethodField()

    def get_activity(self, obj):
        """
        Roles are per transaction, not per person — the same student sells a
        futon in May and claims a desk in August. So we count both.
        """
        done = ["completed", "reviewed"]
        return {
            "sold": Transaction.objects.filter(owner=obj, state__in=done).count(),
            "given": Transaction.objects.filter(owner=obj, state__in=done, mode="free").count(),
            "claimed": Transaction.objects.filter(claimant=obj, state__in=done).count(),
            "listed": Listing.objects.filter(owner=obj).exclude(status="archived").count(),
            "open_requests": Transaction.objects.filter(owner=obj, state="requested").count(),
            "awaiting_me": Transaction.objects.filter(
                models.Q(owner=obj, owner_confirmed_at__isnull=True)
                | models.Q(claimant=obj, claimant_confirmed_at__isnull=True),
                state="accepted",
            ).count(),
        }

    def get_wallet(self, obj):
        w = rewards.get_wallet(obj)
        return {
            "points_posted": w.points_posted,
            "points_pending": w.points_pending,
            "credit_cents": w.credit_cents,
        }


class RegisterSerializer(serializers.ModelSerializer):
    """Account creation is gated on a campus email address."""

    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "latitude", "longitude",
                  "address_label", "avatar_emoji"]

    def validate_email(self, value):
        email = campus.normalize(value)
        if not campus.is_campus_email(email):
            raise serializers.ValidationError(campus.rejection_message())
        if User.objects.filter(campus_email=email).exists():
            raise serializers.ValidationError(
                "There's already an account on that campus address. Try signing in."
            )
        return email

    def create(self, validated):
        password = validated.pop("password")
        email = campus.normalize(validated.get("email", ""))
        user = User(**validated)
        user.campus_email = email
        user.set_password(password)
        user.save()
        rewards.get_wallet(user)
        return user


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "slug", "name", "icon", "avg_weight_kg", "co2e_kg", "est_value_cents"]


class ListingSerializer(serializers.ModelSerializer):
    owner = UserMiniSerializer(read_only=True)
    category_slug = serializers.SlugRelatedField(
        slug_field="slug", source="category", queryset=Category.objects.all(), write_only=True
    )
    category = CategorySerializer(read_only=True)
    price_display = serializers.CharField(read_only=True)
    is_point_eligible = serializers.BooleanField(read_only=True)
    distance_km = serializers.FloatField(read_only=True, required=False)
    match_score = serializers.FloatField(read_only=True, required=False)
    match_reason = serializers.CharField(read_only=True, required=False)
    open_requests = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "owner", "title", "description", "category", "category_slug",
            "mode", "price_cents", "price_display", "trade_for", "condition",
            "photo_url", "latitude", "longitude", "address_label",
            "pickup_deadline", "status", "views", "created_at", "ownership_confirmed",
            "is_point_eligible", "distance_km", "match_score", "match_reason",
            "open_requests",
        ]
        read_only_fields = ["owner", "status", "views", "created_at"]

    def get_open_requests(self, obj):
        return obj.transactions.filter(state="requested").count()


class ReviewSerializer(serializers.ModelSerializer):
    author = UserMiniSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "transaction", "author", "subject", "stars", "on_time",
                  "easy_to_reach", "would_repeat", "body", "created_at"]
        read_only_fields = ["author", "subject", "created_at"]


class TransactionSerializer(serializers.ModelSerializer):
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        source="listing", queryset=Listing.objects.all(), write_only=True
    )
    owner = UserMiniSerializer(read_only=True)
    claimant = UserMiniSerializer(read_only=True)
    my_role = serializers.SerializerMethodField()
    i_confirmed = serializers.SerializerMethodField()
    they_confirmed = serializers.SerializerMethodField()
    i_reviewed = serializers.SerializerMethodField()
    amount_due_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = Transaction
        fields = ["id", "listing", "listing_id", "owner", "claimant", "mode", "state",
                  "message", "pickup_note", "price_cents", "credit_applied_cents",
                  "amount_due_cents", "owner_confirmed_at", "claimant_confirmed_at",
                  "created_at", "my_role", "i_confirmed", "they_confirmed", "i_reviewed",
                  "unread_messages", "message_count",
                  "pickup_at", "pickup_agreed", "pickup_proposed_by_me",
                  "pickup_proposer"]
        read_only_fields = ["owner", "claimant", "mode", "state", "price_cents",
                            "credit_applied_cents", "owner_confirmed_at",
                            "claimant_confirmed_at", "created_at", "pickup_at",
                            "pickup_agreed_at"]

    def _me(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_my_role(self, obj):
        me = self._me()
        if not me or not me.is_authenticated:
            return None
        return "owner" if obj.owner_id == me.id else "claimant"

    def get_i_confirmed(self, obj):
        me = self._me()
        if not me or not me.is_authenticated:
            return False
        return bool(obj.owner_confirmed_at if obj.owner_id == me.id else obj.claimant_confirmed_at)

    def get_they_confirmed(self, obj):
        me = self._me()
        if not me or not me.is_authenticated:
            return False
        return bool(obj.claimant_confirmed_at if obj.owner_id == me.id else obj.owner_confirmed_at)

    pickup_agreed = serializers.SerializerMethodField()
    pickup_proposed_by_me = serializers.SerializerMethodField()
    pickup_proposer = serializers.SerializerMethodField()

    def get_pickup_agreed(self, obj):
        return obj.pickup_agreed_at is not None

    def get_pickup_proposed_by_me(self, obj):
        me = self._me()
        return bool(me and me.is_authenticated and obj.pickup_proposed_by_id == me.id)

    def get_pickup_proposer(self, obj):
        return obj.pickup_proposed_by.username if obj.pickup_proposed_by else None

    unread_messages = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_unread_messages(self, obj):
        me = self._me()
        if not me or not me.is_authenticated:
            return 0
        return obj.messages.filter(read_at__isnull=True).exclude(sender=me).count()

    def get_i_reviewed(self, obj):
        me = self._me()
        if not me or not me.is_authenticated:
            return False
        return obj.reviews.filter(author=me).exists()


class PointEntrySerializer(serializers.ModelSerializer):
    rule_label = serializers.CharField(source="get_rule_display", read_only=True)

    class Meta:
        model = PointEntry
        fields = ["id", "rule", "rule_label", "points", "status", "note",
                  "created_at", "posts_at", "transaction"]


class MessageSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "sender", "body", "mine", "created_at"]
        read_only_fields = ["sender", "created_at"]

    def get_mine(self, obj):
        me = getattr(self.context.get("request"), "user", None)
        return bool(me and me.is_authenticated and obj.sender_id == me.id)


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserMiniSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "actor",
                  "transaction", "is_read", "created_at"]

    def get_is_read(self, obj):
        return obj.read_at is not None


class NeedRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = NeedRequest
        fields = ["id", "raw_text", "parsed", "result_count", "created_at"]
