"""
Distance-based search.

A desk two blocks away beats a slightly better desk across the city, because the
student carrying it has no truck. So distance is a first-class ranking signal,
not a filter applied after the fact.
"""
import math
import re
from datetime import date

from django.db.models import Q

from .models import Listing

EARTH_KM = 6371.0088

# Weights sum to 1.0. Tuned so a perfect text match 3 km away loses to a good
# match 300 m away, which is what students actually want on move-out weekend.
W_TEXT = 0.34
W_DISTANCE = 0.30
W_BUDGET = 0.18
W_URGENCY = 0.10
W_CONDITION = 0.08

STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "to", "of", "in", "on", "my", "i",
    "need", "want", "looking", "some", "any", "with", "near", "under", "am",
    "is", "are", "it", "that", "this", "get", "getting", "would", "like",
}


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def tokenize(text):
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def text_score(tokens, listing):
    """Title hits count triple. Everything is normalised to 0..1."""
    if not tokens:
        return 0.5  # a browse with no query shouldn't punish anything
    title = listing.title.lower()
    body = f"{listing.description} {listing.category.name} {listing.trade_for}".lower()
    hits = 0.0
    for t in tokens:
        if t in title:
            hits += 3
        elif t in body:
            hits += 1
    return min(1.0, hits / (3 * len(tokens)))


def distance_score(km, radius_km):
    """Linear decay to the search radius, then zero."""
    if km >= radius_km:
        return 0.0
    return 1 - (km / radius_km)


def budget_score(listing, max_cents):
    if listing.mode == "free":
        return 1.0
    if max_cents is None:
        return 0.7
    if listing.price_cents > max_cents:
        return 0.0
    if max_cents == 0:
        return 1.0
    # Cheaper is better, but not overwhelmingly so.
    return 1.0 - 0.4 * (listing.price_cents / max_cents)


def urgency_score(listing, needed_by):
    """Rewards listings whose pickup window closes before the student needs it."""
    if not listing.pickup_deadline:
        return 0.4
    today = date.today()
    days_left = (listing.pickup_deadline - today).days
    if days_left < 0:
        return 0.0
    if needed_by:
        return 1.0 if listing.pickup_deadline <= needed_by else 0.3
    # No deadline given: a closing window is still more urgent to surface.
    return max(0.35, 1.0 - min(days_left, 30) / 30)


CONDITION_SCORE = {"new": 1.0, "good": 0.8, "fair": 0.55, "worn": 0.35}


def rank(
    queryset=None,
    text="",
    lat=None,
    lng=None,
    radius_km=8.0,
    max_cents=None,
    needed_by=None,
    modes=None,
    category_slug=None,
    min_condition=None,
    sort="match",
    limit=60,
):
    qs = queryset if queryset is not None else Listing.objects.filter(status="active")
    qs = qs.select_related("owner", "category")

    if modes:
        qs = qs.filter(mode__in=modes)
    if category_slug and category_slug != "all":
        qs = qs.filter(category__slug=category_slug)
    if min_condition:
        order = ["new", "good", "fair", "worn"]
        allowed = order[: order.index(min_condition) + 1]
        qs = qs.filter(condition__in=allowed)
    if text:
        tokens = tokenize(text)
        if tokens:
            q = Q()
            for t in tokens:
                q |= Q(title__icontains=t) | Q(description__icontains=t) | Q(category__name__icontains=t)
            # Keep everything in the radius as a fallback so a typo isn't fatal;
            # weak text matches simply score low rather than disappearing.
            qs = qs.filter(q) if qs.filter(q).exists() else qs

    tokens = tokenize(text)
    results = []
    for listing in qs[:400]:
        km = None
        if lat is not None and lng is not None:
            km = haversine_km(lat, lng, listing.latitude, listing.longitude)
            if km > radius_km:
                continue

        ts = text_score(tokens, listing)
        ds = distance_score(km, radius_km) if km is not None else 0.6
        bs = budget_score(listing, max_cents)
        us = urgency_score(listing, needed_by)
        cs = CONDITION_SCORE.get(listing.condition, 0.6)

        if bs == 0.0 and max_cents is not None:
            continue

        score = W_TEXT * ts + W_DISTANCE * ds + W_BUDGET * bs + W_URGENCY * us + W_CONDITION * cs

        results.append({
            "listing": listing,
            "distance_km": round(km, 2) if km is not None else None,
            "score": round(score, 4),
            "why": {
                "relevance": round(ts, 2),
                "distance": round(ds, 2),
                "budget": round(bs, 2),
                "timing": round(us, 2),
                "condition": round(cs, 2),
            },
        })

    far = float("inf")
    if sort == "distance":
        results.sort(key=lambda r: r["distance_km"] if r["distance_km"] is not None else far)
    elif sort == "newest":
        results.sort(key=lambda r: r["listing"].created_at, reverse=True)
    elif sort == "price_low":
        # Free first, then cheapest. Trades sit with the free items.
        results.sort(key=lambda r: (r["listing"].price_cents, r["distance_km"] or 0))
    elif sort == "price_high":
        results.sort(key=lambda r: -r["listing"].price_cents)
    else:
        results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def explain(row):
    """One line under each card saying why it landed where it did."""
    w = row["why"]
    bits = []
    km = row["distance_km"]
    if km is not None:
        walk = int(km * 1000 / 80)  # ~80 m per minute at a student's walking pace
        bits.append(f"{km} km — about {walk} min walk" if km <= 2 else f"{km} km away")
    if w["relevance"] >= 0.66:
        bits.append("close match")

    listing = row["listing"]
    if listing.mode == "free":
        bits.append("free")
    elif listing.mode == "trade":
        bits.append("open to trades")
    elif w["budget"] >= 0.9:
        bits.append("within budget")

    if w["timing"] >= 0.9:
        bits.append("available before you need it")
    return " · ".join(bits) or "nearby"
