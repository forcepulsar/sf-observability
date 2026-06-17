"""Salesforce authentication — native JWT bearer flow (no external CLI).

Replaces the previous `sf` CLI subprocess approach (which broke when the CLI
changed its `org display --json` output format and masked the access token).
The JWT assertion is built and signed in-process with pyjwt and exchanged for an
access token at the OAuth2 token endpoint. `aud` and the token endpoint use the
org's instance URL (My Domain) — matching the audience the CLI used with
`--instance-url`, which this org's External Client App is configured to accept.

Auth precedence:
  1. JWT/ECA — the supported production method; never expires between runs.
  2. A pre-obtained SF_ACCESS_TOKEN + SF_INSTANCE_URL — for CI/CD that mints a
     token externally.
"""

import logging
import os
import sys
import time

import jwt
import requests
from simple_salesforce import Salesforce

log = logging.getLogger("ingest")

SF_JWT_CLIENT_ID = os.getenv("SF_JWT_CLIENT_ID", "").strip()
SF_JWT_KEY_FILE = os.getenv("SF_JWT_KEY_FILE", "").strip()
SF_JWT_USERNAME = os.getenv("SF_JWT_USERNAME", "").strip()

# JWT assertion lifetime. Salesforce caps this at 3 minutes; the token it
# returns lives much longer, so a short assertion is fine and standard.
_JWT_TTL_SECONDS = 180


def get_sf_client(org_alias: str = "") -> Salesforce:
    """Return an authenticated `Salesforce` client via JWT bearer (or an
    injected access token). Exits the process with a clear message on failure —
    there is no point continuing a run without Salesforce access.

    `org_alias` is accepted for call-site compatibility but unused (it was the
    CLI org alias); auth is driven entirely by environment variables.
    """
    instance_url = os.environ.get(
        "SF_INSTANCE_URL", "https://login.salesforce.com"
    ).strip().rstrip("/")

    # 1. JWT/ECA bearer flow.
    if SF_JWT_CLIENT_ID and SF_JWT_KEY_FILE and SF_JWT_USERNAME:
        if not os.path.exists(SF_JWT_KEY_FILE):
            log.error(f"  SF_JWT_KEY_FILE not found: {SF_JWT_KEY_FILE}")
            sys.exit(1)
        try:
            with open(SF_JWT_KEY_FILE, "r") as f:
                private_key = f.read()
            assertion = jwt.encode(
                {
                    "iss": SF_JWT_CLIENT_ID,
                    "sub": SF_JWT_USERNAME,
                    "aud": instance_url,
                    "exp": int(time.time()) + _JWT_TTL_SECONDS,
                },
                private_key,
                algorithm="RS256",
            )
            resp = requests.post(
                f"{instance_url}/services/oauth2/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                log.error(
                    f"  JWT auth failed (HTTP {resp.status_code}): {resp.text[:300]}"
                )
                sys.exit(1)
            data = resp.json()
            access_token = data.get("access_token")
            resolved_url = data.get("instance_url", instance_url)
            if not access_token:
                log.error("  JWT auth succeeded but no access token returned.")
                sys.exit(1)
            log.info(f"  Auth: JWT/ECA ({SF_JWT_USERNAME})")
            return Salesforce(instance_url=resolved_url, session_id=access_token)
        except SystemExit:
            raise
        except Exception as e:
            log.error(f"  JWT auth failed: {e}")
            sys.exit(1)

    # 2. Pre-obtained access token (CI/CD).
    access_token = os.environ.get("SF_ACCESS_TOKEN", "").strip()
    if access_token and instance_url:
        log.info(f"  Auth: access token ({instance_url})")
        return Salesforce(instance_url=instance_url, session_id=access_token)

    log.error(
        "Salesforce auth not configured. JWT/ECA is required.\n"
        "  Set SF_JWT_CLIENT_ID, SF_JWT_KEY_FILE, and SF_JWT_USERNAME in .env.\n"
        "  See .env.example for step-by-step setup instructions."
    )
    sys.exit(1)
