"""Standalone smoke test for the site auditor - not a pytest suite.

Runs a known slow/legacy site and a modern SaaS/clinic landing page through
audit_lead() and prints the resulting categorization so the thresholds and
Ollama integration can be eyeballed against real sites.
"""

from pathlib import Path
import sys

# Ensure backend root is on sys.path when executed directly as a script
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import json

from app.services.auditor.site_auditor import audit_lead

TEST_URLS = {
    "slow/legacy site": "http://www.spacejam.com",
    "modern SaaS/clinic landing page": "https://www.zocdoc.com",
}


def main() -> None:
    for label, url in TEST_URLS.items():
        print(f"--- {label}: {url} ---")
        result = audit_lead(url)
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
