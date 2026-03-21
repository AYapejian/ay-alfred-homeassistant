"""Domain filter suggestions and smart empty-state helpers."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Optional

from ha_workflow.alfred import AlfredIcon, AlfredItem
from ha_workflow.entities import DOMAIN_REGISTRY, get_domain_config

if TYPE_CHECKING:
    from ha_workflow.entities import Entity
    from ha_workflow.usage import UsageRecord

# Only suggest domains when the query is a single lowercase+underscore token
# of at least 2 characters — avoids false triggers on multi-word fuzzy queries.
_DOMAIN_CANDIDATE_RE = re.compile(r"^[a-z_]{2,}$")


def build_domain_suggestions(
    query: str,
    domain_counts: dict[str, int],
    *,
    max_suggestions: int = 5,
) -> list[AlfredItem]:
    """Return Alfred items suggesting domain filters for *query*.

    Only triggers when *query* looks like a partial domain name (single
    lowercase+underscore token, >= 2 characters) and prefix-matches at
    least one known domain that appears in *domain_counts*.
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

    items: list[AlfredItem] = []
    for domain, count in matches[:max_suggestions]:
        dc = get_domain_config(domain)
        label = "entity" if count == 1 else "entities"
        items.append(
            AlfredItem(
                title=f"Filter: {domain} ({count} {label})",
                subtitle=f"Tab to filter by {domain}",
                icon=AlfredIcon(path=dc.icon_path),
                autocomplete=f"{domain}:",
                uid=f"domain_suggestion_{domain}",
                valid=False,
            )
        )
    return items


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
    from ha_workflow.search import _usage_score  # avoid circular import

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
