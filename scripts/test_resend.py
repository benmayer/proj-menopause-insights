"""Test the Resend key alone WITHOUT sending mail: list verified domains."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import _env  # noqa: F401
import resend

resend.api_key = os.environ["RESEND_API_KEY"]
try:
    domains = resend.Domains.list()
except resend.exceptions.ResendError as e:
    if "restricted to only send" in str(e):
        print("Resend key OK (send-only key, cannot list domains; good least-privilege). Real send test happens in Phase 8.")
        print("EMAIL_FROM domain:", os.environ["EMAIL_FROM"].split("@")[-1])
        sys.exit(0)
    raise
items = domains.get("data", domains) if isinstance(domains, dict) else domains
print("Resend key OK. Domains:", [(d["name"], d["status"]) for d in items] or "none (use onboarding sender, own address only)")
print("EMAIL_FROM domain:", os.environ["EMAIL_FROM"].split("@")[-1])
