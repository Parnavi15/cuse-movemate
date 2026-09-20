"""
Verify a student from the command line.

For when mail isn't configured, or the code is sitting in an inbox you can't
reach mid-demo. Shows the pending code, or marks the account verified outright.

    python manage.py verify_user sshitole@syr.edu          # show the code
    python manage.py verify_user sshitole@syr.edu --force  # just verify them
"""
from django.core.management.base import BaseCommand
from django.db import models

from core import rewards
from core.models import User


class Command(BaseCommand):
    help = "Show a student's pending verification code, or verify them outright."

    def add_arguments(self, parser):
        parser.add_argument("who", help="Username or campus email")
        parser.add_argument("--force", action="store_true",
                            help="Mark verified without a code")

    def handle(self, *args, **opts):
        who = opts["who"].strip().lower()
        user = User.objects.filter(
            models.Q(username__iexact=who)
            | models.Q(campus_email__iexact=who)
            | models.Q(email__iexact=who)
        ).first()

        if not user:
            self.stdout.write(self.style.ERROR(f"No account matching {who!r}."))
            known = User.objects.values_list("username", "campus_email")[:20]
            if known:
                self.stdout.write("\nAccounts on this database:")
                for username, email in known:
                    self.stdout.write(f"  {username:16} {email or '(no campus email)'}")
            return

        if user.is_verified_student and not opts["force"]:
            self.stdout.write(self.style.SUCCESS(
                f"{user.username} is already verified ({user.campus_email})."
            ))
            return

        if opts["force"]:
            user.is_verified_student = True
            user.verification_code = ""
            user.save(update_fields=["is_verified_student", "verification_code"])
            rewards.award(user, "verify", note="Verified student email")
            self.stdout.write(self.style.SUCCESS(
                f"{user.username} is now a verified student. +25 points."
            ))
            return

        if user.verification_code:
            self.stdout.write(self.style.SUCCESS(
                f"\n  Pending code for {user.username} ({user.campus_email}): "
                f"{user.verification_code}\n"
            ))
            self.stdout.write("Enter it in the app, or re-run with --force to skip it.")
        else:
            self.stdout.write(
                f"{user.username} has no pending code. Request one in the app, "
                f"or run with --force."
            )
