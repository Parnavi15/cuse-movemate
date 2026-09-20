import random
import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.core.files.storage import default_storage
from django.utils.dateparse import parse_datetime
from django.db import models
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (action, api_view, parser_classes,
                                       permission_classes)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import campus, geo, mailer, matching, notify, rewards, routing, search
from .models import (Category, Listing, Message, NeedRequest, Notification,
                     Review, Transaction)
from .serializers import (
    CategorySerializer,
    MessageSerializer,
    NotificationSerializer,
    ListingSerializer,
    NeedRequestSerializer,
    PointEntrySerializer,
    RegisterSerializer,
    ReviewSerializer,
    TransactionSerializer,
    UserSerializer,
)

User = get_user_model()


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def issue_verification_code(user):
    """Store a fresh code and email it. Raises mailer.MailError if delivery fails."""
    code = f"{random.randint(0, 999999):06d}"
    user.verification_code = code
    user.verification_sent_at = timezone.now()
    user.save(update_fields=["verification_code", "verification_sent_at"])

    address = user.campus_email or user.email
    mailer.send_verification_code(address, code)
    return code


def verified_student_required(user):
    """Browsing is open. Listing, claiming and redeeming are not."""
    from django.conf import settings

    if not settings.REQUIRE_VERIFIED_STUDENT or user.is_verified_student:
        return None
    return Response(
        {"detail": "Confirm the code sent to your campus email before you can do that.",
         "needs_verification": True},
        status=status.HTTP_403_FORBIDDEN,
    )


def _origin(request):
    """Where to measure distance from: explicit coords, else the student's home."""
    lat = _float(request.query_params.get("lat") or request.data.get("lat"))
    lng = _float(request.query_params.get("lng") or request.data.get("lng"))
    if lat is not None and lng is not None:
        return lat, lng
    user = request.user
    if user.is_authenticated:
        return user.latitude, user.longitude
    from .models import CAMPUS_LAT, CAMPUS_LNG

    return CAMPUS_LAT, CAMPUS_LNG


def _decorate(rows, request):
    """Attach distance, score and a plain-English reason to each listing."""
    out = []
    for row in rows:
        listing = row["listing"]
        listing.distance_km = row["distance_km"]
        listing.match_score = row["score"]
        listing.match_reason = search.explain(row)
        out.append(ListingSerializer(listing, context={"request": request}).data)
    return out


# ==========================================================================
# Auth + verified student identity
# ==========================================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    token, _ = Token.objects.get_or_create(user=user)

    from django.conf import settings

    payload = {
        "token": token.key,
        "user": UserSerializer(user).data,
        "needs_verification": True,
        "email_live": mailer.is_live(),
    }
    try:
        code = issue_verification_code(user)
        payload["detail"] = f"We sent a 6-digit code to {user.campus_email}."
        # Only leak the code when nothing was actually mailed. Once real SMTP
        # is configured the code exists solely in the student's inbox.
        if settings.DEBUG and not mailer.is_live():
            payload["demo_code"] = code
    except mailer.MailError as exc:
        # The account is real; only delivery failed. Let them retry rather than
        # throwing away a valid signup.
        payload["detail"] = "Account created, but the code couldn't be sent."
        payload["mail_error"] = str(exc)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    identifier = (request.data.get("username") or "").strip()
    password = request.data.get("password")

    # Students think of themselves by their campus address, so accept either.
    username = identifier
    if "@" in identifier:
        match = User.objects.filter(campus_email=campus.normalize(identifier)).first()
        if not match:
            match = User.objects.filter(email__iexact=identifier).first()
        if not match:
            return Response(
                {"detail": "No student account on that address."}, status=400
            )
        username = match.username

    user = authenticate(username=username, password=password)
    if not user:
        return Response({"detail": "Wrong username or password."}, status=400)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": UserSerializer(user).data,
        "needs_verification": not user.is_verified_student,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({"detail": "Signed out."})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "PATCH":
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
    rewards.settle(rewards.get_wallet(request.user))
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_request(request):
    """Step one of student verification: send a code to a .edu address."""
    email = campus.normalize(request.data.get("campus_email") or request.user.campus_email)
    if not campus.is_campus_email(email):
        return Response({"detail": campus.rejection_message()}, status=400)
    if User.objects.filter(campus_email=email).exclude(pk=request.user.pk).exists():
        return Response(
            {"detail": "That address belongs to another student account."}, status=400
        )

    request.user.campus_email = email
    request.user.save(update_fields=["campus_email"])

    from django.conf import settings

    try:
        code = issue_verification_code(request.user)
    except mailer.MailError as exc:
        return Response(
            {"detail": f"Couldn't send the email: {exc}"}, status=502
        )

    payload = {
        "detail": (
            f"Code sent to {email}."
            if mailer.is_live()
            else "No mail server is configured, so the code is shown here instead of emailed."
        ),
        "email_live": mailer.is_live(),
    }
    if settings.DEBUG and not mailer.is_live():
        payload["demo_code"] = code
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_confirm(request):
    code = (request.data.get("code") or "").strip()
    user = request.user
    if not user.verification_code or code != user.verification_code:
        return Response({"detail": "That code doesn't match."}, status=400)
    if user.verification_sent_at and timezone.now() - user.verification_sent_at > timedelta(minutes=30):
        return Response({"detail": "Code expired. Request a new one."}, status=400)

    user.is_verified_student = True
    user.verification_code = ""
    user.save(update_fields=["is_verified_student", "verification_code"])
    rewards.award(user, "verify", note="Verified student email")
    return Response({"detail": "You're a verified student.", "user": UserSerializer(user).data})


# ==========================================================================
# Listings
# ==========================================================================

class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    queryset = Listing.objects.select_related("owner", "category")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "related"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        blocked = verified_student_required(request.user)
        if blocked:
            return blocked
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        listing = serializer.save(owner=self.request.user)
        rewards.award_bulk_listing_bonus(self.request.user)
        return listing

    def perform_update(self, serializer):
        if serializer.instance.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("That isn't your listing.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("That isn't your listing.")
        if instance.transactions.exclude(state__in=["rejected", "cancelled"]).exists():
            instance.status = "archived"
            instance.save(update_fields=["status"])
        else:
            instance.delete()

    def list(self, request, *args, **kwargs):
        """Distance-ranked browse. Every query runs through the same scorer."""
        lat, lng = _origin(request)
        rows = search.rank(
            queryset=Listing.objects.filter(status="active"),
            text=request.query_params.get("q", ""),
            lat=lat,
            lng=lng,
            radius_km=_float(request.query_params.get("radius_km"), 8.0),
            max_cents=_int(request.query_params.get("max_cents")),
            needed_by=_date(request.query_params.get("needed_by")),
            modes=request.query_params.getlist("mode") or None,
            category_slug=request.query_params.get("category"),
            min_condition=request.query_params.get("condition"),
            # Browsing with no query? People expect closest first. A search
            # query means they want relevance, so the blended score wins.
            sort=request.query_params.get("sort")
            or ("match" if request.query_params.get("q") else "distance"),
            limit=_int(request.query_params.get("limit"), 60),
        )
        distances = [r["distance_km"] for r in rows if r["distance_km"] is not None]
        return Response({
            "count": len(rows),
            "origin": {"lat": lat, "lng": lng},
            "nearest_km": min(distances) if distances else None,
            "furthest_km": max(distances) if distances else None,
            "results": _decorate(rows, request),
        })

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_object()
        Listing.objects.filter(pk=listing.pk).update(views=models.F("views") + 1)
        listing.refresh_from_db()
        lat, lng = _origin(request)
        listing.distance_km = round(
            search.haversine_km(lat, lng, listing.latitude, listing.longitude), 2
        )
        return Response(ListingSerializer(listing, context={"request": request}).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mine(self, request):
        qs = Listing.objects.filter(owner=request.user).exclude(status="archived")
        return Response(ListingSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def travel(self, request, pk=None):
        """How long it takes to go and get it, on foot, by bike, bus or car."""
        listing = self.get_object()
        lat, lng = _origin(request)
        km = search.haversine_km(lat, lng, listing.latitude, listing.longitude)
        data = routing.travel_options(
            (lat, lng), (listing.latitude, listing.longitude), km
        )
        return Response({
            "straight_km": round(km, 2),
            "destination": listing.address_label,
            **data,
        })

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        """'You might also need' — the companion graph, grounded in real listings."""
        listing = self.get_object()
        lat, lng = _origin(request)
        wanted = matching.companions_for(listing.title, listing.category.slug)

        groups = []
        for term in wanted:
            rows = search.rank(
                queryset=Listing.objects.filter(status="active").exclude(pk=listing.pk),
                text=term,
                lat=lat,
                lng=lng,
                radius_km=10,
                limit=3,
            )
            rows = [r for r in rows if r["why"]["relevance"] > 0.3]
            groups.append({
                "term": term,
                "available": len(rows),
                "listings": _decorate(rows, request),
            })

        groups.sort(key=lambda g: g["available"], reverse=True)
        return Response({"for": listing.title, "suggestions": groups})


@api_view(["GET"])
@permission_classes([AllowAny])
def categories(request):
    return Response(CategorySerializer(Category.objects.all(), many=True).data)


# ==========================================================================
# Smart match: "what do I need?"
# ==========================================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def smart_match(request):
    text = (request.data.get("text") or "").strip()
    if not text:
        return Response({"detail": "Tell us what you're looking for."}, status=400)

    parsed = matching.parse_need(text)
    lat, lng = _origin(request)

    needs = parsed.get("needs") or []
    # Nothing nameable in the sentence: show whatever fits the filters rather
    # than searching for the sentence itself and returning nothing.
    if not needs:
        needs = [{"label": "Available nearby", "text": "", "category": None}]

    groups = []
    seen_ids = set()

    for need in needs:
        rows = search.rank(
            queryset=Listing.objects.filter(status="active"),
            text=need["text"],
            lat=lat,
            lng=lng,
            radius_km=parsed["radius_km"],
            max_cents=parsed["max_cents"],
            needed_by=parsed["needed_by"],
            modes=parsed["modes"],
            category_slug=need.get("category"),
            limit=6,
        )
        # A category or open-ended need has no text to be relevant to, so the
        # relevance floor only applies when the student named something.
        if need["text"]:
            rows = [r for r in rows if r["why"]["relevance"] > 0.25]
        for r in rows:
            seen_ids.add(r["listing"].id)
        groups.append({
            "need": need["label"],
            "found": len(rows),
            "listings": _decorate(rows, request),
        })

    # Show the groups that actually found something first.
    groups.sort(key=lambda g: g["found"], reverse=True)

    # An empty page is never the right answer. If nothing matched, widen the
    # radius, drop the text, and show what students near here actually have.
    # Better to say "not this, but here's what exists" than to say nothing.
    fallback = False
    if not seen_ids:
        rows = search.rank(
            queryset=Listing.objects.filter(status="active"),
            text="",
            lat=lat,
            lng=lng,
            radius_km=max(parsed["radius_km"], 15),
            max_cents=parsed["max_cents"],
            modes=parsed["modes"],
            sort="distance",
            limit=8,
        )
        if rows:
            fallback = True
            groups = [{
                "need": "Nothing matched, but students near you are passing these on",
                "found": len(rows),
                "listings": _decorate(rows, request),
                "is_fallback": True,
            }] + groups

    # Companion items, so the next need is covered too.
    terms = parsed.get("items") or []
    next_up = []
    for term in terms[:3]:
        next_up.extend(matching.companions_for(term))
    next_up = [n for n in dict.fromkeys(next_up) if n not in terms][:5]

    if request.user.is_authenticated:
        NeedRequest.objects.create(
            user=request.user,
            raw_text=text,
            parsed={
                "items": parsed["items"],
                "categories": parsed.get("categories", []),
                "max_cents": parsed["max_cents"],
                "needed_by": parsed["needed_by"].isoformat() if parsed["needed_by"] else None,
                "radius_km": parsed["radius_km"],
                "modes": parsed["modes"],
                "engine": parsed["engine"],
            },
            result_count=len(seen_ids),
        )

    return Response({
        "understood": {
            "items": parsed["items"],
            "categories": parsed.get("categories", []),
            "budget_cents": parsed["max_cents"],
            "needed_by": parsed["needed_by"],
            "radius_km": parsed["radius_km"],
            "modes": parsed["modes"],
            "engine": parsed["engine"],
        },
        "total_found": len(seen_ids),
        "fallback": fallback,
        "groups": groups,
        "you_might_also_need": next_up,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_needs(request):
    return Response(NeedRequestSerializer(request.user.needs.all()[:20], many=True).data)


# ==========================================================================
# Booking flow: request -> accept/reject -> confirm -> review
# ==========================================================================

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Transaction.objects.filter(
            models.Q(owner=user) | models.Q(claimant=user)
        ).select_related("listing__category", "listing__owner", "owner", "claimant")
        role = self.request.query_params.get("role")
        if role == "owner":
            qs = qs.filter(owner=user)
        elif role == "claimant":
            qs = qs.filter(claimant=user)
        state = self.request.query_params.get("state")
        if state:
            qs = qs.filter(state=state)
        return qs

    @db_transaction.atomic
    def create(self, request, *args, **kwargs):
        blocked = verified_student_required(request.user)
        if blocked:
            return blocked

        listing_id = request.data.get("listing_id")
        listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
        if not listing:
            return Response({"detail": "Listing not found."}, status=404)
        if listing.owner == request.user:
            return Response({"detail": "You can't claim your own listing."}, status=400)
        if listing.status != "active":
            return Response({"detail": "That item is no longer available."}, status=400)
        if Transaction.objects.filter(
            listing=listing, claimant=request.user, state__in=["requested", "accepted"]
        ).exists():
            return Response({"detail": "You've already asked for this one."}, status=400)

        # Optional: apply wallet credit, capped at half the price.
        wallet = rewards.get_wallet(request.user)
        credit = _int(request.data.get("credit_cents"), 0) or 0
        credit = min(credit, rewards.max_credit_for(listing.price_cents, wallet))

        txn = Transaction.objects.create(
            listing=listing,
            owner=listing.owner,
            claimant=request.user,
            mode=listing.mode,
            price_cents=listing.price_cents,
            credit_applied_cents=credit,
            message=(request.data.get("message") or "")[:300],
        )
        notify.request_received(txn)
        return Response(
            TransactionSerializer(txn, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _guard(self, txn, user, roles, states):
        role = "owner" if txn.owner_id == user.id else "claimant"
        if role not in roles:
            return Response({"detail": f"Only the {' or '.join(roles)} can do that."}, status=403)
        if txn.state not in states:
            return Response({"detail": f"Can't do that while the request is {txn.state}."}, status=400)
        return None

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner"], ["requested"])
        if err:
            return err
        with db_transaction.atomic():
            txn.state = "accepted"
            txn.pickup_note = (request.data.get("pickup_note") or "")[:200]
            txn.save()
            txn.listing.status = "reserved"
            txn.listing.save(update_fields=["status"])
            # Everyone else waiting on this item is told now, not later.
            losers = list(
                Transaction.objects.filter(listing=txn.listing, state="requested").exclude(pk=txn.pk)
            )
            Transaction.objects.filter(pk__in=[t.pk for t in losers]).update(state="rejected")

        notify.request_accepted(txn)
        # Everyone else waiting on this item hears now, not by refreshing later.
        for loser in losers:
            loser.state = "rejected"
            notify.request_rejected(loser)
        return Response(TransactionSerializer(txn, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner"], ["requested"])
        if err:
            return err
        txn.state = "rejected"
        txn.save(update_fields=["state"])
        notify.request_rejected(txn)
        return Response(TransactionSerializer(txn, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner", "claimant"], ["requested", "accepted"])
        if err:
            return err
        with db_transaction.atomic():
            txn.state = "cancelled"
            txn.save(update_fields=["state"])
            txn.listing.status = "active"
            txn.listing.save(update_fields=["status"])
        return Response(TransactionSerializer(txn, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """
        The only call in the system that creates points.

        One tap from each student. When the second one lands, the transaction
        completes, credit is spent, and the ledger rows are written as pending.
        """
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner", "claimant"], ["accepted"])
        if err:
            return err

        with db_transaction.atomic():
            now = timezone.now()
            if txn.owner_id == request.user.id:
                txn.owner_confirmed_at = txn.owner_confirmed_at or now
            else:
                txn.claimant_confirmed_at = txn.claimant_confirmed_at or now

            both = txn.owner_confirmed_at and txn.claimant_confirmed_at
            if both:
                txn.state = "completed"
                txn.listing.status = "completed"
                txn.listing.save(update_fields=["status"])
                if txn.credit_applied_cents:
                    try:
                        rewards.spend_credit(txn.claimant, txn.credit_applied_cents)
                    except rewards.RedeemError:
                        txn.credit_applied_cents = 0
            txn.save()

            if both:
                rewards.award_for_handoff(txn)

        if both:
            notify.handoff_complete(txn)
        else:
            notify.handoff_pending(txn, request.user)

        data = TransactionSerializer(txn, context={"request": request}).data
        data["blocked_reason"] = rewards.earning_blocked_reason(request.user, txn)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="propose-time")
    def propose_time(self, request, pk=None):
        """
        Suggest a pickup time. Either side can propose; the other agrees.

        Proposing always clears any previous agreement, so a changed time can
        never silently stay "agreed" for the person who didn't change it.
        """
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner", "claimant"], ["requested", "accepted"])
        if err:
            return err

        raw = (request.data.get("pickup_at") or "").strip()
        when = parse_datetime(raw)
        if when is None:
            return Response({"detail": "Give a date and time."}, status=400)
        if timezone.is_naive(when):
            when = timezone.make_aware(when, timezone.get_current_timezone())
        if when < timezone.now() - timedelta(minutes=5):
            return Response({"detail": "Pick a time in the future."}, status=400)
        if when > timezone.now() + timedelta(days=60):
            return Response({"detail": "That's more than two months out."}, status=400)

        deadline = txn.listing.pickup_deadline
        if deadline and when.date() > deadline:
            return Response(
                {"detail": f"The listing's pickup window closes {deadline}."}, status=400
            )

        with db_transaction.atomic():
            txn.pickup_at = when
            txn.pickup_proposed_by = request.user
            txn.pickup_agreed_at = None
            txn.save(update_fields=["pickup_at", "pickup_proposed_by", "pickup_agreed_at"])

        notify.time_proposed(txn, request.user)
        return Response(TransactionSerializer(txn, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="agree-time")
    def agree_time(self, request, pk=None):
        """Agree to the other side's proposal. You can't agree with yourself."""
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner", "claimant"], ["requested", "accepted"])
        if err:
            return err
        if not txn.pickup_at:
            return Response({"detail": "Nobody has suggested a time yet."}, status=400)
        if txn.pickup_proposed_by_id == request.user.id:
            return Response(
                {"detail": "You suggested this one — wait for them to agree."}, status=400
            )

        txn.pickup_agreed_at = timezone.now()
        txn.save(update_fields=["pickup_agreed_at"])
        notify.time_agreed(txn, request.user)
        return Response(TransactionSerializer(txn, context={"request": request}).data)

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        """
        Chat for one handoff. Only the two students involved can read or write,
        which get_queryset already guarantees.
        """
        txn = self.get_object()

        if request.method == "POST":
            body = (request.data.get("body") or "").strip()
            if not body:
                return Response({"detail": "Write something first."}, status=400)
            if len(body) > 1000:
                return Response({"detail": "That message is too long."}, status=400)
            if txn.state in ("rejected", "cancelled"):
                return Response({"detail": "This conversation is closed."}, status=400)

            message = Message.objects.create(
                transaction=txn, sender=request.user, body=body
            )
            other = txn.other_party(request.user)
            notify.notify(
                other,
                "message",
                f"{request.user.username} messaged you about {txn.listing.title}",
                body[:200],
                link="/requests",
                txn=txn,
                actor=request.user,
            )
            return Response(
                MessageSerializer(message, context={"request": request}).data, status=201
            )

        # Reading marks the other side's messages as read.
        txn.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(
            read_at=timezone.now()
        )
        rows = txn.messages.select_related("sender")
        return Response(MessageSerializer(rows, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def dispute(self, request, pk=None):
        """Reports a problem inside the 24h window. Pending points vanish."""
        txn = self.get_object()
        err = self._guard(txn, request.user, ["owner", "claimant"], ["completed", "reviewed"])
        if err:
            return err
        with db_transaction.atomic():
            txn.state = "disputed"
            txn.save(update_fields=["state"])
            rewards.reverse_for_transaction(txn, reason=f"Disputed: {txn.listing.title}")
            txn.listing.status = "active"
            txn.listing.save(update_fields=["status"])
        return Response(TransactionSerializer(txn, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_review(request):
    txn = Transaction.objects.filter(pk=request.data.get("transaction")).first()
    if not txn:
        return Response({"detail": "Transaction not found."}, status=404)
    if request.user.id not in (txn.owner_id, txn.claimant_id):
        return Response({"detail": "You weren't part of that handoff."}, status=403)
    if txn.state not in ("completed", "reviewed"):
        return Response({"detail": "Reviews open once the handoff is confirmed."}, status=400)
    if txn.reviews.filter(author=request.user).exists():
        return Response({"detail": "You've already reviewed this one."}, status=400)

    stars = _int(request.data.get("stars"), 0)
    if stars < 1 or stars > 5:
        return Response({"detail": "Pick 1 to 5 stars."}, status=400)

    subject = txn.other_party(request.user)
    with db_transaction.atomic():
        review = Review.objects.create(
            transaction=txn,
            author=request.user,
            subject=subject,
            stars=stars,
            on_time=bool(request.data.get("on_time", True)),
            easy_to_reach=bool(request.data.get("easy_to_reach", True)),
            would_repeat=bool(request.data.get("would_repeat", True)),
            body=(request.data.get("body") or "")[:400],
        )
        txn.state = "reviewed"
        txn.save(update_fields=["state"])
        subject.recompute_rating()
        rewards.award(request.user, "review", txn, note=f"Reviewed {subject.username}")
        rewards.check_badges(subject)

    notify.review_received(review)

    return Response(ReviewSerializer(review).data, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def user_reviews(request, user_id):
    reviews = Review.objects.filter(subject_id=user_id).select_related("author")[:30]
    return Response(ReviewSerializer(reviews, many=True).data)


# ==========================================================================
# Wallet
# ==========================================================================

# ==========================================================================
# Notifications
# ==========================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications(request):
    qs = request.user.notifications.select_related("actor")
    if request.query_params.get("unread") == "1":
        qs = qs.filter(read_at__isnull=True)
    rows = qs[:40]
    return Response({
        "unread": request.user.notifications.filter(read_at__isnull=True).count(),
        "results": NotificationSerializer(rows, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    updated = request.user.notifications.filter(pk=pk, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return Response({"marked": updated})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notifications_read_all(request):
    updated = request.user.notifications.filter(read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return Response({"marked": updated})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet(request):
    w = rewards.get_wallet(request.user)
    rewards.settle(w)
    w.refresh_from_db()
    return Response({
        "points_posted": w.points_posted,
        "points_pending": w.points_pending,
        "credit_cents": w.credit_cents,
        "lifetime_points": w.lifetime_points,
        "points_per_dollar": rewards.POINTS_PER_DOLLAR,
        "redeem_block": rewards.REDEEM_BLOCK,
        "max_credit_share": rewards.MAX_CREDIT_SHARE,
        "can_redeem": request.user.is_verified_student,
        "weekly_earned": rewards.points_earned_this_week(request.user),
        "weekly_ceiling": rewards.WEEKLY_CEILING,
        "reward_table": rewards.reward_table(),
        "badges": rewards.badge_progress(request.user),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_ledger(request):
    w = rewards.get_wallet(request.user)
    rewards.settle(w)
    entries = w.entries.all()[:50]
    return Response(PointEntrySerializer(entries, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_impact(request):
    rewards.settle(rewards.get_wallet(request.user))
    return Response(rewards.impact_for(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_redeem(request):
    try:
        w = rewards.redeem(request.user, _int(request.data.get("points"), 0))
    except rewards.RedeemError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response({
        "points_posted": w.points_posted,
        "credit_cents": w.credit_cents,
        "detail": "Credit added to your wallet.",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def wallet_settle(request):
    """Demo helper: skips the 24-hour wait so a live demo isn't a cliffhanger."""
    from django.conf import settings

    if not settings.DEBUG:
        return Response({"detail": "Not available."}, status=403)
    rewards.settle(rewards.get_wallet(request.user), force=True)
    return Response({"detail": "Pending points posted."})


@api_view(["GET"])
@permission_classes([AllowAny])
def leaderboard(request):
    top = (
        User.objects.filter(wallet__lifetime_points__gt=0)
        .select_related("wallet")
        .order_by("-wallet__lifetime_points")[:10]
    )
    return Response([
        {
            "username": u.username,
            "avatar_emoji": u.avatar_emoji,
            "points": u.wallet.lifetime_points,
            "items": rewards.metric_value(u, "completed"),
            "verified": u.is_verified_student,
        }
        for u in top
    ])


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/gif": ".gif", "image/heic": ".heic",
}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_photo(request):
    """
    Take a photo straight off a student's phone and hand back a URL.

    Kept separate from listing creation so the form stays plain JSON and the
    photo can be uploaded (and previewed) before anything else is filled in.
    """
    from django.conf import settings

    photo = request.FILES.get("photo")
    if not photo:
        return Response({"detail": "No file received."}, status=400)
    if photo.size > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        return Response({"detail": f"That photo is over {mb} MB. Try a smaller one."}, status=400)

    ext = ALLOWED_IMAGE_TYPES.get((photo.content_type or "").lower())
    if not ext:
        return Response(
            {"detail": "Use a JPG, PNG, WebP or GIF."}, status=400
        )

    name = f"listings/{request.user.id}-{uuid.uuid4().hex[:12]}{ext}"
    saved = default_storage.save(name, photo)
    return Response(
        {"url": request.build_absolute_uri(default_storage.url(saved)), "name": saved},
        status=201,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def geo_reverse(request):
    """Coordinates from the browser's Geolocation API -> a readable place name."""
    lat = _float(request.query_params.get("lat"))
    lng = _float(request.query_params.get("lng"))
    if lat is None or lng is None:
        return Response({"detail": "Need lat and lng."}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return Response({"detail": "Those coordinates aren't on Earth."}, status=400)
    result = geo.reverse(lat, lng)
    return Response({**result, "latitude": lat, "longitude": lng})


@api_view(["GET"])
@permission_classes([AllowAny])
def geo_search(request):
    """Typed address -> coordinates, for students who'd rather not share GPS."""
    results = geo.search(request.query_params.get("q", ""), limit=5)
    return Response({"provider": geo.provider(), "results": results})


@api_view(["GET"])
@permission_classes([AllowAny])
def config(request):
    """The UI reads the campus rule from here rather than hardcoding it."""
    from django.conf import settings

    return Response({
        "student_domains": campus.allowed_domains(),
        "student_domains_display": ", ".join("@" + d for d in campus.allowed_domains()),
        "require_verified": settings.REQUIRE_VERIFIED_STUDENT,
        "geocoder": geo.provider(),
        "email_live": mailer.is_live(),
        "school": "Syracuse University",
        "version": settings.APP_VERSION,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def campus_stats(request):
    """The numbers on the landing page hero."""
    completed = Transaction.objects.filter(state__in=["completed", "reviewed"])
    weight = co2e = 0
    saved = 0
    for t in completed.select_related("listing__category"):
        weight += float(t.listing.category.avg_weight_kg)
        co2e += float(t.listing.category.co2e_kg)
        saved += max(0, t.listing.category.est_value_cents - t.price_cents)
    return Response({
        "items_available": Listing.objects.filter(status="active").count(),
        "items_circulated": completed.count(),
        "students": User.objects.count(),
        "weight_kg": round(weight, 1),
        "co2e_kg": round(co2e, 1),
        "savings_cents": saved,
    })
