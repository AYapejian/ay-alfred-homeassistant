"""Domain filter suggestions and smart empty-state helpers."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Optional

from ha_lib.entities import DOMAIN_REGISTRY, get_domain_config

if TYPE_CHECKING:
    from ha_lib.entities import Entity
    from ha_lib.usage import UsageRecord

# Only suggest domains when the query is a single lowercase+underscore token
# of at least 2 characters — avoids false triggers on multi-word fuzzy queries.
_DOMAIN_CANDIDATE_RE = re.compile(r"^[a-z_]{2,}$")


def get_domain_suggestion_items(
    query: str,
    domain_counts: dict[str, int],
    *,
    max_suggestions: int = 5,
) -> list[tuple[str, str, int, str]]:
    """Return domain suggestion tuples for *query*.

    Returns a list of ``(domain, icon_path, count, autocomplete)`` tuples.
    Only triggers when *query* looks like a partial domain name.

    This is Alfred-agnostic — callers build the actual Alfred items.
    """
    query = query.strip()
    if not query or not _DOMAIN_CANDIDATE_RE.match(query):
        return []

    # Don't suggest if the query already IS a full domain name
    if query in DOMAIN_REGISTRY:
        return []

    matches: list[tuple[str, int]] = []
    for domain, count in domain_counts.items():
        if domain.startswith(query) and domain in DOMAIN_REGISTRY:
            matches.append((domain, count))

    if not matches:
        return []

    # Sort by entity count descending (most populated first)
    matches.sort(key=lambda x: -x[1])

    result: list[tuple[str, str, int, str]] = []
    for domain, count in matches[:max_suggestions]:
        dc = get_domain_config(domain)
        result.append((domain, dc.icon_path, count, f"{domain}:"))

    return result


def sort_by_usage(
    entities: list[Entity],
    usage_stats: Optional[dict[str, UsageRecord]] = None,
    *,
    now: Optional[float] = None,
    max_results: int = 50,
) -> list[Entity]:
    """Sort *entities* by usage score for empty-query display.

    Entities with usage data come first (sorted by usage score descending),
    followed by entities without usage data (sorted alphabetically).
    """
    from ha_lib.search import _usage_score  # avoid circular import

    ts = now if now is not None else time.time()

    if not usage_stats:
        return sorted(entities, key=lambda e: e.friendly_name.lower())[:max_results]

    return sorted(
        entities,
        key=lambda e: (
            -_usage_score(e.entity_id, usage_stats, ts),
            e.friendly_name.lower(),
        ),
    )[:max_results]
