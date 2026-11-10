"""Salesforce authentication — OAuth 2.0 client credentials flow.

The ingest exchanges the External Client App's consumer key + secret for an
access token at the org's My Domain token endpoint. Salesforce runs the session
as the ECA's configured "Run As" user (OAuth Policies → Client Credentials
Flow), so no username, certificate, or private key is involved here.

Replaced the JWT bearer flow (signed assertion + uploaded certificate) to stop
maintaining certificates — same pattern the CH Salesforce org uses for its other
server-to-server integrations.

Auth precedence:
  1. Client credentials — the supported production method; a fresh token is
     minted every run.
  2. A pre-obtained SF_ACCESS_TOKEN + SF_INSTANCE_URL — for CI/CD that mints a
     token externally.
"""

import logging
import os
import sys

import requests
from simple_salesforce import Salesforce

log = logging.getLogger("ingest")

SF_CLIENT_ID = os.getenv("SF_CLIENT_ID", "").strip()
SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET", "").strip()


def get_sf_client(org_alias: str = "") -> Salesforce:
    """Return an authenticated `Salesforce` client via client credentials (or an
    injected access token). Exits the process with a clear message on failure —
    there is no point continuing a run without Salesforce access.

    `org_alias` is accepted for call-site compatibility but unused (it was the
    CLI org alias); auth is driven entirely by environment variables.
    """
    instance_url = os.environ.get("SF_INSTANCE_URL", "").strip().rstrip("/")

    # 1. Client credentials flow. Requires the org's My Domain URL —
    #    login.salesforce.com / test.salesforce.com reject this grant.
    if SF_CLIENT_ID and SF_CLIENT_SECRET:
        if not instance_url:
            log.error("  SF_INSTANCE_URL is required (org My Domain URL).")
            sys.exit(1)
        try:
            resp = requests.post(
                f"{instance_url}/services/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": SF_CLIENT_ID,
                    "client_secret": SF_CLIENT_SECRET,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                log.error(
                    f"  Client credentials auth failed (HTTP {resp.status_code}): "
                    f"{resp.text[:300]}"
                )
                sys.exit(1)
            data = resp.json()
            access_token = data.get("access_token")
            resolved_url = data.get("instance_url", instance_url)
            if not access_token:
                log.error("  Client credentials auth succeeded but no access token returned.")
                sys.exit(1)
            log.info(f"  Auth: client credentials ({resolved_url})")
            return Salesforce(instance_url=resolved_url, session_id=access_token)
        except SystemExit:
            raise
        except Exception as e:
            log.error(f"  Client credentials auth failed: {e}")
            sys.exit(1)

    # 2. Pre-obtained access token (CI/CD).
    access_token = os.environ.get("SF_ACCESS_TOKEN", "").strip()
    if access_token and instance_url:
        log.info(f"  Auth: access token ({instance_url})")
        return Salesforce(instance_url=instance_url, session_id=access_token)

    log.error(
        "Salesforce auth not configured. Client credentials are required.\n"
        "  Set SF_CLIENT_ID, SF_CLIENT_SECRET, and SF_INSTANCE_URL in .env.\n"
        "  See .env.example for setup instructions."
    )
    sys.exit(1)
