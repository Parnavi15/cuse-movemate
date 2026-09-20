"""
Who counts as a student.

One place decides it, so there's no second copy of the rule to drift out of sync.
Subdomains of an allowed domain pass too, because universities hand out addresses
like @g.syr.edu and @mail.syr.edu alongside the plain one.
"""
from django.conf import settings


def allowed_domains():
    return [
        d.strip().lower().lstrip("@")
        for d in settings.ALLOWED_STUDENT_EMAIL_DOMAINS
        if d.strip()
    ]


def normalize(email):
    return (email or "").strip().lower()


def domain_of(email):
    email = normalize(email)
    return email.rsplit("@", 1)[-1] if "@" in email else ""


def is_campus_email(email):
    domain = domain_of(email)
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in allowed_domains())


def rejection_message():
    domains = ", ".join("@" + d for d in allowed_domains())
    return (
        f"Cuse-MoveMate is for students only. Sign up with your university "
        f"email address ({domains})."
    )
