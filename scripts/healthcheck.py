"""Docker container healthcheck script.

Performs a simple HTTP GET against the local API ``/health`` endpoint and
exits with code 0 on success or 1 on failure.

Usage (Dockerfile HEALTHCHECK)::

    HEALTHCHECK CMD python -m scripts.healthcheck
"""

import sys

import httpx

try:
    resp = httpx.get("http://localhost:8000/health", timeout=5)
    resp.raise_for_status()
    sys.exit(0)
except Exception:
    sys.exit(1)
