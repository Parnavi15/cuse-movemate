"""
Seed a demo campus.

A wallet with a history is the difference between a feature and a screenshot.
This leaves the `demo` account one confirm tap away from the payoff moment.

    python manage.py seed --reset
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from core import rewards
from core.models import (Badge, Category, Listing, PointEntry, Review,
                         Transaction, User, Wallet)

CAMPUS = (43.0392, -76.1351)

CATEGORIES = [
    ("furniture", "Furniture", "🪑", 14, 31, 4500),
    ("kitchen", "Kitchen", "🍴", 4, 12, 2800),
    ("electronics", "Electronics", "💻", 2.5, 24, 6000),
    ("books", "Books & supplies", "📚", 1.5, 4, 2200),
    ("tools", "Tools", "🔧", 3, 9, 3000),
    ("sports", "Sports", "🏀", 3, 9, 3000),
    ("party", "Party", "🎉", 2, 5, 1500),
    ("other", "Other", "📦", 2, 5, 1500),
]

BADGES = [
    ("reuse-starter", "Reuse Starter", "🌱", "Your first completed handoff", 1, "completed", 25),
    ("campus-recycler", "Campus Recycler", "♻️", "5 items kept in circulation", 5, "completed", 50),
    ("move-out-hero", "Move-Out Hero", "🎁", "10 items given away free", 10, "given", 100),
    ("trusted-neighbor", "Trusted Neighbor", "🤝", "10 reviews at 4 stars or better", 10, "reviews", 75),
    ("movemate-champion", "MoveMate Champion", "🏆", "25 items kept in circulation", 25, "completed", 250),
]

# Real Syracuse coordinates. Listings are spread from the Quad out to the
# suburbs so the distance filter has something to actually filter.
PLACES = {
    "quad":        ("SU Quad",            43.0392, -76.1351),
    "comstock":    ("Comstock Ave",       43.0369, -76.1330),
    "euclid":      ("Euclid Ave",         43.0448, -76.1389),
    "ostrom":      ("Ostrom Ave",         43.0421, -76.1301),
    "ackerman":    ("Ackerman Ave",       43.0393, -76.1289),
    "westcott":    ("Westcott St",        43.0413, -76.1230),
    "southcampus": ("South Campus",       43.0290, -76.1244),
    "armory":      ("Armory Square",      43.0481, -76.1540),
    "tipphill":    ("Tipperary Hill",     43.0530, -76.1780),
    "eastwood":    ("Eastwood",           43.0570, -76.1000),
    "dewitt":      ("DeWitt",             43.0384, -76.0730),
    "liverpool":   ("Liverpool",          43.1065, -76.2177),
    "fayetteville":("Fayetteville",       43.0292, -76.0050),
    "camillus":    ("Camillus",           43.0400, -76.3050),
}

STUDENTS = [
    ("demo", "🧑‍🎓", "comstock", True),
    ("maya", "🎨", "euclid", True),
    ("devin", "🎧", "ostrom", True),
    ("priya", "📗", "southcampus", True),
    ("jules", "🛠️", "westcott", True),
    ("sam", "⚽", "ackerman", True),
]

# title, category, mode, price_cents, condition, owner, location, description
ITEMS = [
    ("IKEA study desk", "furniture", "free", 0, "good", "maya", "euclid",
     "Solid white desk, one small scratch on the left side. Comes apart with an allen key."),
    ("Desk chair, adjustable", "furniture", "sale", 1500, "good", "maya", "euclid",
     "Mesh back, height adjustable, wheels roll fine. Sitting in my living room until Friday."),
    ("Mini fridge, 3.2 cu ft", "kitchen", "sale", 4000, "good", "devin", "ostrom",
     "Used two semesters, cleaned out and defrosted. Freezer compartment works."),
    ("KitchenAid stand mixer", "kitchen", "sale", 8500, "new", "priya", "liverpool",
     "Barely used, still has the box and the dough hook. Moving out of state."),
    ("Instant Pot Duo 6qt", "kitchen", "sale", 2000, "good", "sam", "ackerman",
     "Six quart, all the accessories. Made a lot of rice in this thing."),
    ("Pots and pans set", "kitchen", "free", 0, "fair", "devin", "euclid",
     "Four pieces, non-stick is worn on the small pan but the rest are fine."),
    ("DeWalt cordless drill", "tools", "sale", 3000, "good", "jules", "westcott",
     "Two batteries and a charger. Great for hanging shelves in an apartment."),
    ("Paint brush set", "tools", "free", 0, "good", "jules", "armory",
     "Five brushes, cleaned. Left over from painting my room last month."),
    ("Paint roller and tray", "tools", "free", 0, "fair", "jules", "eastwood",
     "Roller frame, two covers and a tray. Washed and dried."),
    ("Painter's tape, 2 rolls", "tools", "free", 0, "new", "maya", "westcott",
     "Unopened blue tape, 1.88 inch. Didn't end up needing it."),
    ("Drop cloth, canvas", "tools", "free", 0, "good", "jules", "tipphill",
     "9x12 canvas drop cloth, a few paint spots. Folds down small."),
    ("24 inch monitor", "electronics", "sale", 5500, "good", "devin", "ostrom",
     "1080p, HDMI and VGA. Stand included, no dead pixels."),
    ("HDMI cable, 6ft", "electronics", "free", 0, "good", "sam", "quad",
     "Works fine, I just have four of them."),
    ("Power strip, 6 outlet", "electronics", "free", 0, "good", "priya", "southcampus",
     "Surge protected, 4ft cord."),
    ("Desk lamp", "furniture", "free", 0, "good", "priya", "comstock",
     "Small clip-on LED lamp, three brightness settings."),
    ("Electric scooter", "sports", "sale", 12000, "good", "sam", "dewitt",
     "Gets about 12 miles on a charge. Selling because I'm graduating."),
    ("Bike lock, U-lock", "sports", "trade", 0, "good", "jules", "westcott",
     "Two keys. Would trade for a floor pump or a helmet."),
    ("Storage bins, set of 3", "other", "free", 0, "good", "maya", "ostrom",
     "Clear plastic with lids. Stack nicely under a bed."),
    ("Organic Chemistry textbook", "books", "sale", 2500, "fair", "priya", "fayetteville",
     "8th edition, some highlighting in chapters 3 through 7."),
    ("TI-84 calculator", "books", "sale", 3500, "good", "priya", "camillus",
     "Works perfectly, comes with the cover and batteries."),
    ("Folding table", "party", "free", 0, "fair", "sam", "comstock",
     "6ft plastic folding table. One leg latch is stiff but it holds."),
    ("String lights, 2 sets", "party", "free", 0, "good", "devin", "ackerman",
     "Warm white, 30ft each. Both tested."),

    # --- Other ---
    ("Clothes hangers, 20 pack", "other", "free", 0, "good", "maya", "euclid",
     "Mix of plastic and velvet. All in one piece."),
    ("Vacuum cleaner, upright", "other", "sale", 2500, "good", "jules", "westcott",
     "Bagless, filter rinsed last month. Cord is about 20ft."),
    ("Laundry basket + drying rack", "other", "free", 0, "fair", "priya", "southcampus",
     "Basket has a small crack on one handle, rack folds flat."),
    ("Box fan, 20 inch", "other", "sale", 1000, "good", "sam", "armory",
     "Three speeds, all working. Got me through two Syracuse Septembers."),
    ("Full-length mirror", "other", "free", 0, "good", "devin", "ostrom",
     "Leans against a wall, no mounting needed. No chips."),
    ("Iron and ironing board", "other", "sale", 1500, "good", "maya", "eastwood",
     "Steam iron works fine, board is the tabletop kind."),

    # --- Party ---
    ("Bluetooth party speaker", "party", "sale", 4500, "good", "devin", "ackerman",
     "Loud enough for a backyard. Holds about 8 hours of charge."),
    ("Folding chairs, set of 4", "party", "sale", 2000, "fair", "sam", "comstock",
     "Metal frame, one has a scuffed seat. They stack."),
    ("Cooler, 48 quart", "party", "free", 0, "good", "jules", "dewitt",
     "Wheels and a handle. Holds a lot of ice, cleaned out."),
    ("String lights, 50ft warm white", "party", "free", 0, "new", "priya", "quad",
     "Never hung these — still coiled in the box."),
    ("Serving bowls and tablecloth", "party", "free", 0, "good", "maya", "tipphill",
     "Four big plastic bowls and one washable tablecloth."),
    ("Card table, folding", "party", "sale", 1200, "good", "priya", "liverpool",
     "34 inch square, legs lock. Good for games or extra counter space."),

    # --- Electronics ---
    ("Wireless keyboard and mouse", "electronics", "free", 0, "good", "devin", "ostrom",
     "Logitech combo, one USB receiver. Takes AA batteries, not included."),
    ("Laptop stand and USB-C hub", "electronics", "sale", 1800, "good", "priya", "southcampus",
     "Aluminium stand plus a 4-port hub. Saved my neck during finals."),
    ("Desk speakers, 2.0", "electronics", "sale", 2200, "good", "sam", "westcott",
     "Wired 3.5mm, no static. Better than a laptop by a mile."),

    # --- Sports ---
    ("Yoga mat and block", "sports", "free", 0, "fair", "maya", "euclid",
     "Mat has some wear at the knees but no tears. Block is fine."),
    ("Dumbbells, 2 x 10lb", "sports", "sale", 1800, "good", "jules", "eastwood",
     "Hex rubber, no rust. Heavy to carry, so bring a bag."),

    # --- Furniture ---
    ("Bookshelf, 3 shelf", "furniture", "free", 0, "fair", "sam", "armory",
     "Particle board, one shelf has a small sag. Holds textbooks fine."),
    ("Floor lamp", "furniture", "sale", 1200, "good", "devin", "fayetteville",
     "Standing lamp with a dimmer. Bulb included."),
]

PHOTO = "https://placehold.co/600x400/E1590A/FFFFFF?text="


class Command(BaseCommand):
    help = "Seed a demo campus with students, listings and wallet history."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Wipe demo data first")

    @db_transaction.atomic
    def handle(self, *args, **opts):
        random.seed(11)

        if opts["reset"]:
            self.stdout.write("Clearing existing demo data…")
            from core.models import Notification

            Notification.objects.all().delete()
            Review.objects.all().delete()
            PointEntry.objects.all().delete()
            Transaction.objects.all().delete()
            Listing.objects.all().delete()
            Wallet.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # ---- categories with impact constants -------------------------
        cats = {}
        for slug, name, icon, kg, co2, cents in CATEGORIES:
            cat, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "avg_weight_kg": kg,
                          "co2e_kg": co2, "est_value_cents": cents},
            )
            cats[slug] = cat

        for slug, name, icon, desc, threshold, metric, bonus in BADGES:
            Badge.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "description": desc,
                          "threshold": threshold, "metric": metric, "bonus_points": bonus},
            )

        # ---- students -------------------------------------------------
        users = {}
        for username, emoji, place, verified in STUDENTS:
            label, lat, lng = PLACES[place]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@syr.edu",
                    "campus_email": f"{username}@syr.edu",
                    "is_verified_student": verified,
                    "avatar_emoji": emoji,
                    "address_label": label,
                    "latitude": lat,
                    "longitude": lng,
                    "bio": "Moving out in May.",
                },
            )
            if created:
                user.set_password("movemate")
                user.save()
            rewards.get_wallet(user)
            users[username] = user

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@syr.edu", "movemate")

        # ---- listings -------------------------------------------------
        today = timezone.now().date()
        listings = {}
        for title, cat_slug, mode, price, condition, owner, place, desc in ITEMS:
            label, lat, lng = PLACES[place]
            listing, _ = Listing.objects.get_or_create(
                title=title,
                owner=users[owner],
                defaults={
                    "description": desc,
                    "category": cats[cat_slug],
                    "mode": mode,
                    "price_cents": price,
                    "condition": condition,
                    "trade_for": "a floor pump or helmet" if mode == "trade" else "",
                    "photo_url": PHOTO + title.split(",")[0].replace(" ", "+"),
                    "latitude": lat + random.uniform(-0.002, 0.002),
                    "longitude": lng + random.uniform(-0.002, 0.002),
                    "address_label": label,
                    "pickup_deadline": today + timedelta(days=random.randint(3, 21)),
                    "ownership_confirmed": True,
                },
            )
            listings[title] = listing

        # ---- history: completed handoffs so the wallet has a past ------
        history = [
            ("Desk lamp", "priya", "demo"),
            ("HDMI cable, 6ft", "sam", "demo"),
            ("Storage bins, set of 3", "maya", "demo"),
            ("String lights, 2 sets", "devin", "demo"),
            ("Pots and pans set", "devin", "demo"),
            ("Power strip, 6 outlet", "priya", "demo"),
            ("Painter's tape, 2 rolls", "maya", "devin"),
            ("Folding table", "sam", "priya"),
        ]

        for title, owner, claimant in history:
            listing = listings[title]
            if Transaction.objects.filter(listing=listing).exists():
                continue
            txn = Transaction.objects.create(
                listing=listing,
                owner=users[owner],
                claimant=users[claimant],
                mode=listing.mode,
                price_cents=listing.price_cents,
                state="accepted",
                message="Can I grab this after class?",
            )
            txn.owner_confirmed_at = timezone.now() - timedelta(days=random.randint(2, 20))
            txn.claimant_confirmed_at = txn.owner_confirmed_at + timedelta(minutes=8)
            txn.state = "completed"
            txn.save()
            listing.status = "completed"
            listing.save(update_fields=["status"])
            rewards.award_for_handoff(txn)

            # Reviews both ways, so ratings and review points are real.
            for author, subject in ((users[claimant], users[owner]), (users[owner], users[claimant])):
                if Review.objects.filter(transaction=txn, author=author).exists():
                    continue
                Review.objects.create(
                    transaction=txn, author=author, subject=subject,
                    stars=random.choice([4, 5, 5, 5]),
                    body="Easy pickup, exactly as described.",
                )
                rewards.award(author, "review", txn, note=f"Reviewed {subject.username}")
            txn.state = "reviewed"
            txn.save(update_fields=["state"])
            users[owner].recompute_rating()
            users[claimant].recompute_rating()

        # Everything historical has cleared its dispute window by now.
        rewards.settle(force=True)
        for u in users.values():
            rewards.check_badges(u)
        rewards.settle(force=True)

        # ---- one live request waiting on demo's approval ---------------
        pending_listing = listings["IKEA study desk"]
        if not Transaction.objects.filter(listing=pending_listing).exists():
            pending_listing.owner = users["demo"]
            pending_listing.save(update_fields=["owner"])
            Transaction.objects.create(
                listing=pending_listing,
                owner=users["demo"],
                claimant=users["maya"],
                mode="free",
                message="Moving into an apartment on Friday and this would be perfect.",
            )

        demo_wallet = rewards.get_wallet(users["demo"])
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {Listing.objects.count()} listings across {User.objects.count()} students."
        ))
        self.stdout.write(
            f"demo wallet: {demo_wallet.points_posted} posted, "
            f"{demo_wallet.points_pending} pending, "
            f"${demo_wallet.credit_cents / 100:.2f} credit"
        )
        self.stdout.write("\nSign in as any of: " + ", ".join(users) + "  (password: movemate)")
        self.stdout.write("Django admin: admin / movemate")
        self.stdout.write(self.style.WARNING(
            "\nDemo path: sign in as demo -> Requests -> accept Maya's desk request "
            "-> confirm handoff -> watch the wallet.\n"
        ))
