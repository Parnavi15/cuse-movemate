"""
Turning coordinates into places, and places into coordinates.

Two providers behind one interface:
  1. Google Maps, when GOOGLE_MAPS_API_KEY is set. Best quality.
  2. Nominatim (OpenStreetMap), always. No key, no billing account.

The browser already gives us exact coordinates through the Geolocation API, so
this is only about the human-readable half: showing "Euclid Ave, Syracuse"
instead of "43.0448, -76.1389", and letting a student type an address when they
would rather not share GPS.

Both calls go through the Django server rather than the browser. The API key
never reaches the client, which is the whole reason to proxy it.
"""
import json
import time
import urllib.parse
import urllib.request

from django.conf import settings

TIMEOUT = 6
USER_AGENT = "Cuse-MoveMate/1.0 (student marketplace; hackathon project)"

# ---------------------------------------------------------------------------
# Campus gazetteer.
#
# Students search for "South Campus", "the Quad", "Ernie Davis" — names that
# either aren't in OpenStreetMap or sit under something official nobody says
# out loud. A geocoder answers those questions badly, and badly is worse than
# not at all: searching "south campus" was returning Westcott.
#
# So: check this table first, fall through to the geocoder for real addresses.
# ---------------------------------------------------------------------------
CAMPUS_PLACES = [
    ("South Campus", ["south campus", "skytop", "slocum heights", "goldstein"], 43.0290, -76.1244),
    ("SU Quad", ["quad", "hall of languages", "hendricks", "bird library", "main campus"], 43.0392, -76.1351),
    ("Ernie Davis Hall", ["ernie davis", "edh"], 43.0405, -76.1372),
    ("Brewster/Boland", ["brewster", "boland", "brockway"], 43.0362, -76.1281),
    ("Sadler Hall", ["sadler", "lawrinson", "mount olympus"], 43.0374, -76.1288),
    ("Shaw Hall", ["shaw hall", "shaw"], 43.0398, -76.1319),
    ("Watson Hall", ["watson hall", "watson"], 43.0387, -76.1330),
    ("Day Hall", ["day hall", "flint hall"], 43.0378, -76.1301),
    ("Comstock Ave", ["comstock"], 43.0369, -76.1330),
    ("Euclid Ave", ["euclid"], 43.0448, -76.1389),
    ("Ostrom Ave", ["ostrom"], 43.0421, -76.1301),
    ("Ackerman Ave", ["ackerman"], 43.0393, -76.1289),
    ("Westcott St", ["westcott"], 43.0413, -76.1230),
    ("Marshall St", ["marshall street", "marshall st", "m street"], 43.0400, -76.1373),
    ("Carrier Dome", ["carrier dome", "jma dome", "the dome"], 43.0362, -76.1363),
    ("Schine Student Center", ["schine"], 43.0390, -76.1362),
    ("Whitman School", ["whitman"], 43.0378, -76.1353),
    ("Newhouse", ["newhouse"], 43.0369, -76.1345),
    ("Link Hall", ["link hall", "engineering"], 43.0384, -76.1345),
    ("Armory Square", ["armory", "downtown syracuse", "downtown"], 43.0481, -76.1540),
    ("Tipperary Hill", ["tipp hill", "tipperary"], 43.0530, -76.1780),
    ("Eastwood", ["eastwood"], 43.0570, -76.1000),
    ("DeWitt", ["dewitt", "de witt"], 43.0384, -76.0730),
    ("Liverpool", ["liverpool"], 43.1065, -76.2177),
    ("Fayetteville", ["fayetteville"], 43.0292, -76.0050),
    ("Camillus", ["camillus"], 43.0400, -76.3050),
    ("ESF", ["esf", "forestry"], 43.0342, -76.1353),
    ("Upstate Medical", ["upstate", "medical center", "hospital"], 43.0420, -76.1420),
]


def campus_matches(text, limit=5):
    """Known campus places whose name or nickname contains the query."""
    q = " ".join((text or "").lower().split())
    if len(q) < 2:
        return []
    hits = []
    for label, aliases, lat, lng in CAMPUS_PLACES:
        names = [label.lower()] + aliases
        # Exact alias first, then prefix, then anywhere — so "shaw" beats
        # "shaw hall" only when it should.
        score = None
        for n in names:
            if n == q:
                score = 0
            elif n.startswith(q) and score is None:
                score = 1
            elif q in n and score is None:
                score = 2
        if score is not None:
            hits.append((score, {
                "label": label,
                "address": f"{label}, Syracuse, NY",
                "latitude": lat,
                "longitude": lng,
                "campus": True,
            }))
    hits.sort(key=lambda h: h[0])
    return [h[1] for h in hits[:limit]]


# Syracuse, so a blank search doesn't wander off to another continent.
BIAS_LAT, BIAS_LNG = 43.0392, -76.1351
BIAS_BOX = "-76.45,42.90,-75.85,43.25"  # lng_min, lat_min, lng_max, lat_max

# Geocoding results barely change, and both providers rate-limit. A process
# local cache is enough for a demo and keeps Nominatim happy.
_cache = {}
_last_call = [0.0]


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _throttle():
    """Nominatim's usage policy is one request per second. Respect it."""
    wait = 1.0 - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _google_key():
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "") or ""


def provider():
    return "google" if _google_key() else "nominatim"


# --------------------------------------------------------------------------
# Reverse: coordinates -> a name a student would recognise
# --------------------------------------------------------------------------

def _short_label(parts, name=None):
    """
    Students say "Euclid Ave" or "South Campus", not "742 Euclid Avenue,
    Syracuse, NY 13210".

    The matched place's own name wins over the neighbourhood it sits in —
    labelling a South Campus result "Westcott" because that's the surrounding
    neighbourhood is worse than useless.
    """
    if name:
        return name
    for key in ("neighbourhood", "neighborhood", "road", "suburb", "hamlet", "city"):
        if parts.get(key):
            return parts[key]
    return "Near campus"


def reverse_google(lat, lng):
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode({
        "latlng": f"{lat},{lng}",
        "key": _google_key(),
        "result_type": "neighborhood|route|sublocality|locality",
    })
    data = _get_json(url)
    results = data.get("results") or []
    if not results:
        return None
    top = results[0]
    parts = {}
    for comp in top.get("address_components", []):
        for t in comp.get("types", []):
            parts.setdefault(t, comp.get("short_name"))
    label = (
        parts.get("neighborhood")
        or parts.get("route")
        or parts.get("sublocality")
        or parts.get("locality")
        or "Near campus"
    )
    return {"label": label, "address": top.get("formatted_address", ""), "source": "google"}


def reverse_nominatim(lat, lng):
    _throttle()
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
        "lat": lat, "lon": lng, "format": "jsonv2", "zoom": 16, "addressdetails": 1,
    })
    data = _get_json(url)
    parts = data.get("address") or {}
    return {
        "label": _short_label(parts),
        "address": data.get("display_name", ""),
        "source": "nominatim",
    }


def reverse(lat, lng):
    key = f"r:{round(float(lat), 4)},{round(float(lng), 4)}"
    if key in _cache:
        return _cache[key]
    try:
        result = reverse_google(lat, lng) if _google_key() else reverse_nominatim(lat, lng)
    except Exception:
        result = None
    # Never fail the signup form over a geocoder. The coordinates are what
    # distance search actually needs; the label is a convenience.
    result = result or {"label": "Near campus", "address": "", "source": "fallback"}
    _cache[key] = result
    return result


# --------------------------------------------------------------------------
# Forward: typed address -> coordinates
# --------------------------------------------------------------------------

def search_google(text, limit):
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode({
        "address": text,
        "key": _google_key(),
        "bounds": "42.90,-76.45|43.25,-75.85",
        "region": "us",
    })
    data = _get_json(url)
    out = []
    for r in (data.get("results") or [])[:limit]:
        loc = r["geometry"]["location"]
        out.append({
            "label": r.get("formatted_address", "").split(",")[0],
            "address": r.get("formatted_address", ""),
            "latitude": loc["lat"],
            "longitude": loc["lng"],
        })
    return out


def search_nominatim(text, limit):
    _throttle()
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": text, "format": "jsonv2", "limit": limit,
        "addressdetails": 1, "viewbox": BIAS_BOX, "bounded": 0, "countrycodes": "us",
    })
    out = []
    for r in _get_json(url):
        parts = r.get("address") or {}
        out.append({
            "label": _short_label(parts, r.get("name")) or text,
            "address": r.get("display_name", ""),
            "latitude": float(r["lat"]),
            "longitude": float(r["lon"]),
        })
    return out


def search(text, limit=5):
    text = (text or "").strip()
    if len(text) < 2:
        return []

    # Campus places first, and if any match we stop there. Going on to the
    # geocoder would add a network round trip (up to 6s, or a full timeout when
    # the wifi is down) to a question we have already answered correctly — and
    # answered better, since OSM doesn't index "South Campus" or "Skytop".
    campus = campus_matches(text, limit)
    if campus:
        return campus

    # Bias toward Syracuse unless the student typed a city themselves.
    query = text if "," in text else f"{text}, Syracuse, NY"
    key = f"s:{query.lower()}:{limit}"
    if key in _cache:
        return _cache[key]
    try:
        results = search_google(query, limit) if _google_key() else search_nominatim(query, limit)
    except Exception:
        results = []
    _cache[key] = results
    return results
