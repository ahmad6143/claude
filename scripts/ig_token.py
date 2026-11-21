"""Turn a short-lived Facebook user token into the IG_USER_ID and a long-lived Page token.

Usage (values via environment so they stay out of shell history):
  APP_ID=... APP_SECRET=... SHORT_TOKEN=... python scripts/ig_token.py

Get SHORT_TOKEN from Meta's Graph API Explorer with these permissions:
  instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement
"""
import os
import sys

import requests

G = f"https://graph.facebook.com/{os.getenv('IG_API_VERSION', 'v26.0')}"


def get(path, **params):
    data = requests.get(f"{G}/{path}", params=params, timeout=30).json()
    if "error" in data:
        sys.exit(f"Meta API error: {data['error'].get('message')}")
    return data


def main():
    try:
        app_id, secret, short = os.environ["APP_ID"], os.environ["APP_SECRET"], os.environ["SHORT_TOKEN"]
    except KeyError as exc:
        sys.exit(f"Set {exc.args[0]} in the environment (see the docstring).")
    long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                    client_secret=secret, fb_exchange_token=short)["access_token"]
    pages = get("me/accounts", fields="name,access_token,instagram_business_account",
                access_token=long_user).get("data", [])
    found = False
    for p in pages:
        ig = (p.get("instagram_business_account") or {}).get("id")
        if ig:
            found = True
            print(f"\nFacebook Page: {p['name']}\nIG_USER_ID={ig}\nIG_ACCESS_TOKEN={p['access_token']}")
    if not found:
        sys.exit("No Page with a linked Instagram professional account was found for this token.")


if __name__ == "__main__":
    main()
