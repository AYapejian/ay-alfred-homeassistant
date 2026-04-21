"""Query parser — decomposes raw Alfred input into structured search parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ha_workflow.entities import DOMAIN_REGISTRY

# ---------------------------------------------------------------------------
# Parsed query
# ---------------------------------------------------------------------------

_DOMAIN_PREFIX_RE = re.compile(r"^([a-z_]+):(.*)$")
# Entity IDs are ``<domain>.<object_id>`` where both sides are lowercase
# identifiers / digits / underscores.  We require a ``.`` and a known domain
# so quick-exec only fires on well-formed entity references.
_ENTITY_ID_RE = re.compile(r"^([a-z_]+)\.([a-z0-9_]+)$")


@dataclass(frozen=True)
class ParsedQuery:
    """Structured representation of a user's search input.

    Attributes
    ----------
    mode:
        ``"fuzzy"`` for standard fuzzy search, ``"regex"`` for regex matching,
        ``"domain_browse"`` when a domain filter is given with no text, or
        ``"quick_exec"`` when the input is an entity_id optionally followed
        by a parameter string (e.g. ``light.foo brightness:80,color:red``).
    text:
        The search text after extracting modifiers.
    domain_filter:
        Domain name to restrict results (e.g. ``"light"``), or ``None``.
    regex_pattern:
        Regex pattern string extracted from ``/pattern/`` syntax, or ``None``.
    entity_id:
        For ``quick_exec`` mode — the fully-qualified entity ID.
    raw_params:
        For ``quick_exec`` mode — the raw comma-separated param string
        (may be empty, meaning "fire the default action with no params").
    """

    mode: str  # "fuzzy" | "regex" | "domain_browse" | "quick_exec"
    text: str
    domain_filter: Optional[str]
    regex_pattern: Optional[str]
    entity_id: Optional[str] = None
    raw_params: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_query(raw: str) -> ParsedQuery:
    """Parse *raw* query text into a :class:`ParsedQuery`.

    Supports four syntaxes:

    1. ``/pattern/`` — regex search
    2. ``<domain>.<object_id> [params]`` — quick-exec (needs a known domain
       and, at call time, an entity that actually exists in the cache)
    3. ``domain:text`` — domain-filtered fuzzy search (or browse if *text* empty)
    4. Plain text — standard fuzzy search

    Quick-exec detection here only validates *shape* — whether the entity
    exists in the cache is the caller's responsibility, so typos cleanly
    fall back to fuzzy search.
    """
    stripped = raw.strip()

    # 1. Regex syntax: /pattern/
    if len(stripped) >= 2 and stripped.startswith("/") and stripped.endswith("/"):
        pattern = stripped[1:-1]
        return ParsedQuery(
            mode="regex",
            text="",
            domain_filter=None,
            regex_pattern=pattern,
        )

    # 2. Quick-exec: <entity_id> [params]
    first, _, rest = stripped.partition(" ")
    em = _ENTITY_ID_RE.match(first)
    if em and em.group(1) in DOMAIN_REGISTRY:
        return ParsedQuery(
            mode="quick_exec",
            text="",
            domain_filter=None,
            regex_pattern=None,
            entity_id=first,
            raw_params=rest.strip(),
        )

    # 3. Domain filter syntax: domain:text
    m = _DOMAIN_PREFIX_RE.match(stripped)
    if m:
        candidate_domain = m.group(1)
        remainder = m.group(2).strip()
        if candidate_domain in DOMAIN_REGISTRY:
            if remainder:
                return ParsedQuery(
                    mode="fuzzy",
                    text=remainder,
                    domain_filter=candidate_domain,
                    regex_pattern=None,
                )
            return ParsedQuery(
                mode="domain_browse",
                text="",
                domain_filter=candidate_domain,
                regex_pattern=None,
            )
        # Invalid domain prefix — fall through to plain fuzzy search

    # 4. Plain fuzzy search
    return ParsedQuery(
        mode="fuzzy",
        text=stripped,
        domain_filter=None,
        regex_pattern=None,
    )
