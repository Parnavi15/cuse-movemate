"""
"What do I need?" — turning a sentence into structured requirements.

Two implementations behind one function:
  1. Claude, when ANTHROPIC_API_KEY is set. Handles real phrasing.
  2. A deterministic parser, always. Handles the demo when the wifi dies.

The fallback is not a toy. Judge-facing demos should never depend on a network
call, so the rule parser covers the phrasings students actually type.
"""
import json
import os
import re
from datetime import date, timedelta

from .models import Category

# --------------------------------------------------------------------------
# Companion graph: what a student needs *next*
# --------------------------------------------------------------------------
# Searching for a paint brush should surface the roller, the tape and the
# drop cloth, because the person about to paint a dorm room needs all four.

COMPANIONS = {
    "paint brush": ["paint roller", "painter's tape", "drop cloth", "paint tray", "leftover paint"],
    "paint roller": ["paint brush", "painter's tape", "drop cloth", "paint tray"],
    "desk": ["desk chair", "desk lamp", "monitor", "power strip", "desk organizer"],
    "desk chair": ["desk", "floor mat", "seat cushion", "desk lamp"],
    "bed": ["mattress topper", "bed frame", "sheets", "pillow", "mattress protector"],
    "mattress": ["mattress topper", "sheets", "bed frame", "pillow"],
    "mini fridge": ["microwave", "storage bins", "surge protector"],
    "microwave": ["mini fridge", "dishes", "measuring cups"],
    "monitor": ["hdmi cable", "monitor stand", "keyboard", "mouse", "power strip"],
    "bike": ["bike lock", "helmet", "bike pump", "bike light"],
    "pots": ["pans", "cooking utensils", "dish rack", "cutting board"],
    "pan": ["pots", "spatula", "cutting board", "dish rack"],
    "vacuum": ["cleaning supplies", "trash can", "broom"],
    "textbook": ["notebook", "highlighters", "backpack", "calculator"],
    "lamp": ["light bulbs", "extension cord", "power strip"],
    "tv": ["hdmi cable", "tv stand", "streaming stick", "surge protector"],
    "couch": ["coffee table", "throw pillows", "rug", "floor lamp"],
    "printer": ["printer paper", "ink cartridges", "usb cable"],
    "drill": ["drill bits", "screwdriver set", "wall anchors", "level"],
    "storage bin": ["hangers", "shelving", "moving boxes", "packing tape"],
}

# Starter kits for the "I'm moving in and need everything" case.
MOVE_IN_KITS = {
    "apartment": ["desk", "desk chair", "mini fridge", "microwave", "pots and pans", "lamp", "storage bins"],
    "dorm": ["mini fridge", "desk lamp", "storage bins", "shower caddy", "mattress topper", "power strip"],
    "kitchen": ["pots and pans", "microwave", "dishes", "cooking utensils", "dish rack", "toaster"],
}

# Whole phrases that mean "a category", not one object. Without these,
# "kitchen supplies" matches nothing and the student sees an empty page.
PHRASE_CATEGORY = {
    "kitchen supplies": "kitchen",
    "kitchen stuff": "kitchen",
    "kitchen things": "kitchen",
    "kitchen essentials": "kitchen",
    "cooking supplies": "kitchen",
    "cookware": "kitchen",
    "school supplies": "books",
    "study supplies": "books",
    "office supplies": "books",
    "cleaning supplies": "other",
    "power tools": "tools",
    "hand tools": "tools",
    "gym equipment": "sports",
    "party supplies": "party",
    "decorations": "party",
}

# A bare category name counts as a need too.
CATEGORY_WORDS = {
    "kitchen": "kitchen",
    "cookware": "kitchen",
    "furniture": "furniture",
    "furnishings": "furniture",
    "electronics": "electronics",
    "tech": "electronics",
    "textbooks": "books",
    "stationery": "books",
    "tools": "tools",
    "hardware": "tools",
    "sports": "sports",
    "fitness": "sports",
    "party": "party",
}

# Phrases that mean "set me up", used only when nothing specific was named.
KIT_PHRASES = {
    "dorm room": "dorm",
    "dorm": "dorm",
    "residence hall": "dorm",
    "first apartment": "apartment",
    "new apartment": "apartment",
    "apartment": "apartment",
    "kitchen": "kitchen",
}

CATEGORY_HINTS = {
    "furniture": [
        "desk", "chair", "table", "couch", "sofa", "shelf", "shelves", "shelving",
        "dresser", "bed", "futon", "nightstand", "bookcase", "mirror", "rug",
        "lamp", "stool", "bench", "wardrobe", "drawer",
    ],
    "kitchen": [
        "fridge", "refrigerator", "freezer", "microwave", "oven", "stove",
        "pot", "pots", "pan", "pans", "skillet", "saucepan", "dish", "dishes",
        "kettle", "toaster", "blender", "mixer", "cutlery", "silverware",
        "plate", "plates", "bowl", "bowls", "mug", "cup", "glass", "glasses",
        "knife", "knives", "cutting board", "chopping board", "peeler",
        "spatula", "whisk", "ladle", "strainer", "colander", "grater",
        "tupperware", "container", "containers", "utensil", "utensils",
        "coffee maker", "rice cooker", "air fryer", "dish rack", "cookware",
    ],
    "electronics": [
        "monitor", "laptop", "computer", "tv", "television", "printer",
        "speaker", "speakers", "headphone", "headphones", "earbuds",
        "keyboard", "mouse", "cable", "charger", "console", "router",
        "webcam", "hard drive", "power strip", "extension cord", "adapter",
    ],
    "books": [
        "textbook", "textbooks", "book", "books", "notebook", "calculator",
        "binder", "stationery", "highlighter", "planner", "backpack", "folder",
    ],
    "tools": [
        "drill", "hammer", "screwdriver", "wrench", "toolkit", "tool",
        "paint", "brush", "roller", "ladder", "pliers", "tape measure",
        "saw", "level", "sandpaper", "drop cloth", "wall anchors",
    ],
    "sports": [
        "bike", "bicycle", "skateboard", "weights", "dumbbell", "yoga",
        "racket", "ball", "helmet", "scooter", "skates", "treadmill", "mat",
    ],
    "party": [
        "string lights", "decor", "decoration", "cooler", "folding table",
        "banner", "speaker", "tablecloth",
    ],
    "other": [
        "hanger", "hangers", "storage bin", "storage bins", "iron",
        "vacuum", "fan", "heater", "humidifier", "trash can", "laundry basket",
        "shower caddy", "towel", "curtain", "blanket", "pillow",
    ],
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# --------------------------------------------------------------------------
# Rule-based parser
# --------------------------------------------------------------------------

def _parse_budget(text):
    m = re.search(r"(?:under|below|less than|max|up to|budget of|within)\s*\$?\s*(\d+(?:\.\d{1,2})?)", text)
    if m:
        return int(float(m.group(1)) * 100)
    m = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)\s*(?:or less|max|budget)?", text)
    if m:
        return int(float(m.group(1)) * 100)
    if re.search(r"\b(free|no cost|giveaway|giving away|donat)", text):
        return 0
    return None


def _parse_deadline(text):
    today = date.today()
    if re.search(r"\b(today|asap|right now|tonight)\b", text):
        return today
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1)
    m = re.search(r"\b(?:before|by|within)\s+(\d+)\s+days?\b", text)
    if m:
        return today + timedelta(days=int(m.group(1)))
    if re.search(r"\b(this week|end of the week)\b", text):
        return today + timedelta(days=(6 - today.weekday()))
    if re.search(r"\bnext week\b", text):
        return today + timedelta(days=14)
    if re.search(r"\b(this weekend)\b", text):
        return today + timedelta(days=(5 - today.weekday()) % 7)
    for name, idx in WEEKDAYS.items():
        if re.search(rf"\b(?:before|by|on)?\s*{name}\b", text):
            delta = (idx - today.weekday()) % 7 or 7
            return today + timedelta(days=delta)
    if re.search(r"\b(move[- ]?in|moving in)\b", text):
        return today + timedelta(days=14)
    return None


def _parse_radius(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(km|kilometer|mile|mi)\b", text)
    if m:
        value = float(m.group(1))
        return value * 1.60934 if m.group(2).startswith("mi") else value
    if re.search(r"\b(walking distance|on campus|near campus|close by|nearby)\b", text):
        return 2.0
    return 8.0


def _parse_items(text):
    """Specific objects the student named."""
    found = []
    for key in sorted(COMPANIONS.keys(), key=len, reverse=True):
        if key in text and key not in found:
            found.append(key)
    for cat, words in CATEGORY_HINTS.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}s?\b", text) and word not in found:
                found.append(word)
    # "paint brush" already covers "paint" and "brush", and "bowl" covers
    # "bowls" — drop the redundancies so one need isn't three result groups.
    found = [f for f in found if not any(f != o and f in o.split() for o in found)]
    found = [f for f in found if f + "s" not in found]
    return found[:8]


def _parse_categories(text):
    """Whole categories the student asked for: 'kitchen supplies', 'tools'."""
    cats = []
    for phrase, cat in PHRASE_CATEGORY.items():
        if phrase in text and cat not in cats:
            cats.append(cat)
    for word, cat in CATEGORY_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text) and cat not in cats:
            cats.append(cat)
    return cats[:4]


def _parse_kit(text):
    """'Free stuff for a dorm room' means a starter kit, not a literal search."""
    for phrase, kit in sorted(KIT_PHRASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return MOVE_IN_KITS.get(kit, [])
    return []


def build_needs(items, categories):
    """
    One search per thing the student wants.

    A need is either a specific object or a whole category. Empty means
    'show me anything that fits the filters', which is the right answer to
    "looking for free stuff" — far better than searching for that sentence.
    """
    needs = [{"label": i, "text": i, "category": None} for i in items]
    names = {
        "kitchen": "Kitchen supplies", "furniture": "Furniture",
        "electronics": "Electronics", "books": "Books & supplies",
        "tools": "Tools", "sports": "Sports", "party": "Party", "other": "Other",
    }
    for c in categories:
        needs.append({"label": names.get(c, c.title()), "text": "", "category": c})
    return needs


def _parse_modes(text):
    if re.search(r"\b(free|giveaway|giving away|donat)\b", text):
        return ["free", "trade"]
    if re.search(r"\btrade|swap\b", text):
        return ["trade", "free"]
    return ["free", "sale", "trade"]


def _guess_category(items):
    for item in items:
        for cat, words in CATEGORY_HINTS.items():
            if any(w in item for w in words):
                return cat
    return None


def rule_parse(text):
    low = (text or "").lower()
    items = _parse_items(low)
    categories = _parse_categories(low)

    # A named item implies its category, so a miss on the exact word still
    # shows the shelf it would sit on. "knife" -> also search Kitchen.
    if items and not categories:
        guess = _guess_category(items)
        if guess:
            categories = [guess]

    # Nothing specific named? Fall back to a starter kit, then to "anything".
    if not items and not categories:
        items = _parse_kit(low)

    return {
        "items": items,
        "categories": categories,
        "needs": build_needs(items, categories),
        "query": " ".join(items) if items else low[:80],
        "max_cents": _parse_budget(low),
        "needed_by": _parse_deadline(low),
        "radius_km": _parse_radius(low),
        "modes": _parse_modes(low),
        "category": _guess_category(items),
        "engine": "rules",
    }


# --------------------------------------------------------------------------
# Claude parser (optional)
# --------------------------------------------------------------------------

PROMPT = """You turn a student's move-in request into structured search requirements.

Return ONLY a JSON object, no markdown fences, no commentary, with these keys:
  items: array of short item names the student is asking for (max 8)
  max_cents: integer budget ceiling in cents, or null
  needed_by_days: integer days from today they need it by, or null
  radius_km: number, how far they'd travel (default 8, use 2 for "near campus")
  modes: array from ["free","sale","trade"]
  category: one of ["furniture","kitchen","electronics","books","tools","sports","party","other"] or null

Student request: {text}"""


def claude_parse(text):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=500,
            messages=[{"role": "user", "content": PROMPT.format(text=text)}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text")
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
    except Exception:
        return None

    needed_by = None
    if data.get("needed_by_days") is not None:
        needed_by = date.today() + timedelta(days=int(data["needed_by_days"]))

    items = [str(i) for i in (data.get("items") or [])][:8]
    cat = data.get("category")
    categories = [cat] if cat and not items else []
    return {
        "items": items,
        "categories": categories,
        "needs": build_needs(items, categories),
        "query": " ".join(items) or text[:80],
        "max_cents": data.get("max_cents"),
        "needed_by": needed_by,
        "radius_km": float(data.get("radius_km") or 8),
        "modes": data.get("modes") or ["free", "sale", "trade"],
        "category": data.get("category"),
        "engine": "claude",
    }


def parse_need(text):
    """Claude first, rules always. The demo never depends on the network."""
    parsed = claude_parse(text)
    if parsed and parsed.get("needs"):
        return parsed
    return rule_parse(text)


# --------------------------------------------------------------------------
# Companion recommendations
# --------------------------------------------------------------------------

def companions_for(title, category_slug=None, limit=5):
    """What a student searching for this is likely to need next."""
    low = (title or "").lower()
    out = []
    for key, values in COMPANIONS.items():
        if key in low:
            out.extend(values)
    if not out and category_slug:
        siblings = {
            "furniture": ["desk lamp", "storage bins", "rug", "floor mirror"],
            "kitchen": ["dish rack", "cooking utensils", "storage containers"],
            "electronics": ["power strip", "hdmi cable", "surge protector"],
            "books": ["notebook", "highlighters", "backpack"],
            "tools": ["screwdriver set", "wall anchors", "work gloves"],
            "sports": ["water bottle", "gym bag", "helmet"],
            "party": ["cooler", "folding chairs", "string lights"],
        }
        out = siblings.get(category_slug, [])
    seen, result = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result[:limit]


def category_for_slug(slug):
    return Category.objects.filter(slug=slug).first()
