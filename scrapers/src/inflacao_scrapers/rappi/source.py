"""Bounded public HTML fetching for inspection; no credentials, APIs or submission writes."""

from dataclasses import dataclass
from datetime import UTC, datetime

from .document import public_url


@dataclass(frozen=True)
class Capture:
    source: str
    observed_at: datetime
    cache: str | None = None


def fetch_page(requester, url):
    public_url(url)
    response = requester.request(
        "GET", url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}
    )
    if response.status_code != 200:
        raise ValueError(f"Rappi HTTP {response.status_code}; inspection blocked")
    age = response.headers.get("Age", "0")
    if not age.isascii() or not age.isdigit() or int(age) > 0:
        raise ValueError("Rappi returned aged/invalid cache metadata; fresh measurement unverified")
    if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
        raise ValueError("Unexpected Rappi content type")
    if len(response.content) > 8 * 1024 * 1024:
        raise ValueError("Rappi HTML exceeds inspection size limit")
    return Capture(response.text, datetime.now(UTC), response.headers.get("X-Cache"))
