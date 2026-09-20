"""
Create a verified student account in one line.

For testing the two-sided flow without bouncing through signup and email:

    python manage.py create_student pranavi
    python manage.py create_student pranavi --at euclid --password movemate
"""
from django.core.management.base import BaseCommand

from core import rewards
from core.models import User

# The same campus spots the seed uses, so distances look sensible.
PLACES = {
    "quad": ("SU Quad", 43.0392, -76.1351),
    "comstock": ("Comstock Ave", 43.0369, -76.1330),
    "euclid": ("Euclid Ave", 43.0448, -76.1389),
    "ostrom": ("Ostrom Ave", 43.0421, -76.1301),
    "ackerman": ("Ackerman Ave", 43.0393, -76.1289),
    "westcott": ("Westcott St", 43.0413, -76.1230),
    "southcampus": ("South Campus", 43.0290, -76.1244),
    "armory": ("Armory Square", 43.0481, -76.1540),
}


class Command(BaseCommand):
    help = "Create (or update) a verified student account for testing."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--email", help="Defaults to <username>@syr.edu")
        parser.add_argument("--password", default="movemate")
        parser.add_argument("--at", default="euclid", choices=sorted(PLACES),
                            help="Where they live (affects distance search)")
        parser.add_argument("--emoji", default="🧑‍🎓")

    def handle(self, *args, **opts):
        username = opts["username"].strip().lower()
        email = (opts["email"] or f"{username}@syr.edu").strip().lower()
        label, lat, lng = PLACES[opts["at"]]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "campus_email": email},
        )
        user.email = email
        user.campus_email = email
        user.is_verified_student = True
        user.verification_code = ""
        user.avatar_emoji = opts["emoji"]
        user.address_label = label
        user.latitude = lat
        user.longitude = lng
        user.set_password(opts["password"])
        user.save()

        rewards.get_wallet(user)
        if created:
            rewards.award(user, "verify", note="Verified student email")

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"\n  {verb} {username} ({email}) — verified student\n"
        ))
        self.stdout.write(f"  password: {opts['password']}")
        self.stdout.write(f"  lives at: {label}\n")
        self.stdout.write(self.style.WARNING(
            "\n  Sign in as them in a private window so both accounts stay live.\n"
        ))
