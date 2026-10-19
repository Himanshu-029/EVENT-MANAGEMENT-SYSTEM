import requests
from django.conf import settings


def verify_turnstile(token):
    if not token or not settings.TURNSTILE_SECRET_KEY:
        return False

    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("success", False)

    except (requests.RequestException, ValueError):
        return False