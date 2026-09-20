"""
How long it takes to actually go and get the thing.

A straight-line distance tells a student almost nothing. "14 minutes on foot"
or "no bus route, you'll need a car" is what decides whether they claim a desk.

Two sources, same output shape:
  1. Google Distance Matrix when GOOGLE_MAPS_API_KEY is set. Real road
     distances, real transit schedules.
  2. A local estimate otherwise. Clearly labelled as an estimate so nobody
     plans a bus trip around a number we made up.

Either way the "Open in Maps" links are plain Google Maps URLs, which need no
key and no billing account at all.
"""
import json
import urllib.parse
import urllib.request

from django.conf import settings

TIMEOUT = 6

MODES = [
    {"key": "walking", "label": "Walk", "icon": "walk"},
    {"key": "bicycling", "label": "Bike", "icon": "bike"},
    {"key": "transit", "label": "Bus", "icon": "bus"},
    {"key": "driving", "label": "Drive", "icon": "car"},
]

# Straight-line distance understates a real route. Syracuse is a grid, so
# roughly a third longer once you follow actual streets.
ROAD_FACTOR = 1.3

# Average speeds in km/h, plus fixed overhead in minutes (waiting, parking).
LOCAL = {
    "walking": (4.8, 0),
    "bicycling": (15.0, 2),
    "transit": (18.0, 9),   # a bus you didn't plan around means a real wait
    "driving": (30.0, 4),   # city speeds, plus finding a parking spot
}


def _key():
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "") or ""


def maps_url(origin, destination, mode):
    """A plain Google Maps directions link. No key, works everywhere."""
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode({
        "api": 1,
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "travelmode": mode,
    })


def _human_minutes(minutes):
    minutes = int(round(minutes))
    if minutes < 1:
        return "under a minute"
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} hr" if rest == 0 else f"{hours} hr {rest} min"


def _local_estimates(straight_km, origin, destination):
    road_km = straight_km * ROAD_FACTOR
    out = []
    for mode in MODES:
        speed, overhead = LOCAL[mode["key"]]
        minutes = (road_km / speed) * 60 + overhead
        out.append({
            **mode,
            "distance_km": round(road_km, 2),
            "duration_min": int(round(minutes)),
            "duration_text": _human_minutes(minutes),
            "estimated": True,
            "url": maps_url(origin, destination, mode["key"]),
        })
    return out


def _google_estimates(origin, destination):
    results = []
    for mode in MODES:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json?" + urllib.parse.urlencode({
            "origins": f"{origin[0]},{origin[1]}",
            "destinations": f"{destination[0]},{destination[1]}",
            "mode": mode["key"],
            "units": "metric",
            "key": _key(),
        })
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cuse-MoveMate/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            element = data["rows"][0]["elements"][0]
            if element.get("status") != "OK":
                # No transit route at 2am, for instance. Say so rather than
                # inventing a number.
                results.append({
                    **mode, "distance_km": None, "duration_min": None,
                    "duration_text": "No route", "estimated": False,
                    "url": maps_url(origin, destination, mode["key"]),
                })
                continue
            results.append({
                **mode,
                "distance_km": round(element["distance"]["value"] / 1000, 2),
                "duration_min": int(round(element["duration"]["value"] / 60)),
                "duration_text": element["duration"]["text"],
                "estimated": False,
                "url": maps_url(origin, destination, mode["key"]),
            })
        except Exception:
            return None  # fall back to local estimates wholesale
    return results


def travel_options(origin, destination, straight_km):
    """
    origin and destination are (lat, lng) tuples.
    Returns a list of modes, each with a duration and a Maps link.
    """
    if _key():
        google = _google_estimates(origin, destination)
        if google:
            return {"source": "google", "modes": google}
    return {"source": "estimate", "modes": _local_estimates(straight_km, origin, destination)}
