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


@dataclass(frozen=True)
class ParsedQuery:
    """Structured representation of a user's search input.

    Attributes
    ----------
    mode:
        ``"fuzzy"`` for standard fuzzy search, ``"regex"`` for regex matching,
        or ``"domain_browse"`` when a domain filter is given with no text.
    text:
        The search text after extracting modifiers.
    domain_filter:
        Domain name to restrict results (e.g. ``"light"``), or ``None``.
    regex_pattern:
        Regex pattern string extracted from ``/pattern/`` syntax, or ``None``.
    """

    mode: str  # "fuzzy" | "regex" | "domain_browse"
    text: str
    domain_filter: Optional[str]
    regex_pattern: Optional[str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_query(raw: str) -> ParsedQuery:
    """Parse *raw* query text into a :class:`ParsedQuery`.

    Supports three syntaxes:

    1. ``/pattern/`` — regex search
    2. ``domain:text`` — domain-filtered fuzzy search (or browse if *text* empty)
    3. Plain text — standard fuzzy search
    """
    stripped = raw.strip()

    # 1. Regex syntax: /pattern/
    if (
        len(stripped) >= 2
        and stripped.startswith("/")
        and stripped.endswith("/")
    ):
        pattern = stripped[1:-1]
        return ParsedQuery(
            mode="regex",
            text="",
            domain_filter=None,
            regex_pattern=pattern,
        )

    # 2. Domain filter syntax: domain:text
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

    # 3. Plain fuzzy search
    return ParsedQuery(
        mode="fuzzy",
        text=stripped,
        domain_filter=None,
        regex_pattern=None,
    )
