"""
Check mail delivery before you find out on stage that it's broken.

    python manage.py test_email sshitole@syr.edu
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core import mailer


class Command(BaseCommand):
    help = "Send a test verification code to an address."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Where to send the test")

    def handle(self, *args, **opts):
        address = opts["email"]

        self.stdout.write("Mail configuration")
        self.stdout.write(f"  backend  {settings.EMAIL_BACKEND.rsplit('.', 2)[-2]}")
        self.stdout.write(f"  host     {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"  user     {settings.EMAIL_HOST_USER or '(none)'}")
        self.stdout.write(f"  from     {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"  tls/ssl  {settings.EMAIL_USE_TLS}/{settings.EMAIL_USE_SSL}\n")

        if not mailer.is_live():
            self.stdout.write(self.style.WARNING(
                "EMAIL_HOST_USER is not set, so nothing will actually be sent.\n"
                "The message is printed below instead.\n"
            ))

        try:
            mailer.send_verification_code(address, "123456")
        except mailer.MailError as exc:
            self.stdout.write(self.style.ERROR(f"\nFailed: {exc}\n"))
            self.stdout.write(self.hint(str(exc)))
            return

        self.stdout.write(self.style.SUCCESS(f"\nSent to {address}. Check the inbox and spam."))

    def hint(self, error):
        low = error.lower()
        if "username and password not accepted" in low or "authentication" in low or "535" in low:
            return (
                "That's an authentication failure. For Gmail you need a 16-character\n"
                "App Password, not your normal password — turn on 2-Step Verification\n"
                "first, then create one at myaccount.google.com/apppasswords.\n"
                "Paste it without spaces."
            )
        if "ssl" in low or "wrong version" in low:
            return "Port/encryption mismatch. Use 587 with EMAIL_USE_TLS=1, or 465 with EMAIL_USE_SSL=1."
        if "timed out" in low or "connection" in low:
            return "Couldn't reach the mail server. Some campus and conference wifi blocks outbound SMTP — try a phone hotspot."
        return "Check EMAIL_HOST, EMAIL_PORT and the credentials."
