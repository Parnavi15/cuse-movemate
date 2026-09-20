"""
Sending the verification code to a student's real campus inbox.

Delivery is configured entirely through environment variables. With no SMTP
credentials set, Django's console backend prints the message instead, so the
project still runs for anyone who clones it without a mail account.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

log = logging.getLogger(__name__)

SUBJECT = "Your Cuse-MoveMate verification code"

TEXT = """Your Cuse-MoveMate code is {code}

Enter it in the app to confirm you're a student. It expires in 30 minutes.

Verifying lets you list items, claim items and redeem MovePoints, and it's
worth 25 points on its own.

If you didn't sign up for Cuse-MoveMate, you can ignore this email.
"""

HTML = """\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:24px;background:#F4F3F1;
               font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#22262A;">
    <div style="max-width:480px;margin:0 auto;background:#fff;
                border:1px solid #E4E1DD;border-radius:14px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#F76900,#E1590A 55%,#B8460A);
                  color:#fff;padding:22px 24px;">
        <div style="font-size:20px;font-weight:800;">&#9851; Cuse-MoveMate</div>
        <div style="opacity:.92;font-size:14px;margin-top:2px;">
          One student's move-out is another student's move-in
        </div>
      </div>

      <div style="padding:26px 24px;">
        <p style="margin:0 0 6px;font-size:15px;">Your verification code is</p>
        <div style="font-size:40px;font-weight:800;letter-spacing:10px;
                    color:#E1590A;margin:10px 0 18px;">{code}</div>
        <p style="margin:0 0 14px;font-size:15px;line-height:1.55;">
          Enter it in the app to confirm you're a student. It expires in 30 minutes.
        </p>
        <p style="margin:0;font-size:15px;line-height:1.55;">
          Verifying lets you list items, claim items and redeem MovePoints &mdash;
          and it's worth <b>25 points</b> on its own.
        </p>
      </div>

      <div style="padding:16px 24px;border-top:1px solid #E4E1DD;
                  font-size:13px;color:#757D84;">
        Didn't sign up for Cuse-MoveMate? You can ignore this email.
      </div>
    </div>
  </body>
</html>
"""


class MailError(Exception):
    pass


def is_live():
    """True when real SMTP credentials are configured."""
    return bool(getattr(settings, "EMAIL_HOST_USER", ""))


def send_verification_code(email, code):
    message = EmailMultiAlternatives(
        subject=SUBJECT,
        body=TEXT.format(code=code),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    message.attach_alternative(HTML.format(code=code), "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        # Surface the real reason. A silent failure here looks like a broken
        # code to the student, which is the worst possible way to fail.
        log.exception("Verification email to %s failed", email)
        raise MailError(str(exc)) from exc
    return True
