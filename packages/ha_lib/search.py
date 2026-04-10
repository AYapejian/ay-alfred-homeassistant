"""Fuzzy search over Home Assistant entities."""

from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING, Optional

from ha_lib.entities import Entity

if TYPE_CHECKING:
    from ha_lib.usage import UsageRecord

# ---------------------------------------------------------------------------
# Scoring tiers
# ---------------------------------------------------------------------------

_SCORE_EXACT = 100
_SCORE_PREFIX = 80
_SCORE_WORD_BOUNDARY = 60
_SCORE_SUBSTRING = 40
_SCORE_CHAR_SEQUENCE = 20

# ---------------------------------------------------------------------------
# Field weights
# ---------------------------------------------------------------------------

_WEIGHT_FRIENDLY_NAME = 3.0
_WEIGHT_ENTITY_ID = 2.0
_WEIGHT_AREA_NAME = 1.5
_WEIGHT_DEVICE_CLASS = 1.0
_WEIGHT_ATTRIBUTES = 0.5

# Usage boost
_USAGE_WEIGHT = 10.0
_RECENCY_HALF_LIFE = 86400.0  # 24 hours in seconds

# ---------------------------------------------------------------------------
# Low-level scoring helpers
# ---------------------------------------------------------------------------

_WORD_SPLIT = re.compile(r"[\s_.\-]+")


def _matches_char_sequence(text: str, query: str) -> bool:
    """Return ``True`` if every character in *query* appears in *text* in order."""
    it = iter(text)
    return all(c in it for c in query)


def _score_field(field: str, query: str) -> int:
    """Score a single *field* against *query*.  Returns 0 for no match."""
    field_lower = field.lower()
    query_lower = query.lower()

    if field_lower == query_lower:
        return _SCORE_EXACT

    if field_lower.startswith(query_lower):
        return _SCORE_PREFIX

    words = _WORD_SPLIT.split(field_lower)
    if any(w.startswith(query_lower) for w in words):
        return _SCORE_WORD_BOUNDARY

    if query_lower in field_lower:
        return _SCORE_SUBSTRING

    if _matches_char_sequence(field_lower, query_lower):
        return _SCORE_CHAR_SEQUENCE

    return 0


# ---------------------------------------------------------------------------
# Entity scoring
# ---------------------------------------------------------------------------


def _score_entity(entity: Entity, query: str) -> float:
    """Compute a weighted relevance score for *entity* against *query*."""
    score = 0.0

    # Friendly name — highest weight
    score += _score_field(entity.friendly_name, query) * _WEIGHT_FRIENDLY_NAME

    # Entity ID — medium weight; also try the object_id part after the dot
    eid_score = max(
        _score_field(entity.entity_id, query),
        _score_field(entity.entity_id.split(".", 1)[-1], query),
    )
    score += eid_score * _WEIGHT_ENTITY_ID

    # Device class — lower weight
    device_class = entity.device_class
    if device_class:
        score += _score_field(device_class, query) * _WEIGHT_DEVICE_CLASS

    # Area name — from the entity registry, not HA state attributes
    if entity.area_name:
        score += _score_field(entity.area_name, query) * _WEIGHT_AREA_NAME

    return score


def _score_entity_multi(entity: Entity, query: str) -> float:
    """Score with multi-word support.  Each word must match *something*."""
    words = query.split()
    if not words:
        return 0.0
    if len(words) == 1:
        return _score_entity(entity, words[0])

    word_scores: list[float] = []
    for word in words:
        s = _score_entity(entity, word)
        if s == 0:
            return 0.0
        word_scores.append(s)
    return sum(word_scores)


# ---------------------------------------------------------------------------
# Usage boost
# ---------------------------------------------------------------------------


def _usage_score(
    entity_id: str,
    usage_stats: dict[str, UsageRecord],
    now: float,
) -> float:
    """Compute a usage boost from frequency and recency."""
    record = usage_stats.get(entity_id)
    if record is None:
        return 0.0
    freq: float = math.log(record.use_count + 1)
    age = max(now - record.last_used_at, 0.0)
    recency = 2.0 ** (-age / _RECENCY_HALF_LIFE)
    result: float = (0.7 * freq + 0.3 * recency) * _USAGE_WEIGHT
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def regex_search(
    entities: list[Entity],
    pattern: str,
    *,
    max_results: int = 50,
) -> list[Entity]:
    """Search *entities* by *pattern* against ``entity_id`` and ``friendly_name``.

    Returns up to *max_results* matching entities in original order.
    Raises :class:`re.error` if *pattern* is not a valid regex.
    """
    compiled = re.compile(pattern, re.IGNORECASE)
    results: list[Entity] = []
    for entity in entities:
        if compiled.search(entity.entity_id) or compiled.search(entity.friendly_name):
            results.append(entity)
            if len(results) >= max_results:
                break
    return results


def fuzzy_search(
    entities: list[Entity],
    query: str,
    *,
    max_results: int = 50,
    usage_stats: Optional[dict[str, UsageRecord]] = None,
    now: Optional[float] = None,
) -> list[Entity]:
    """Score and rank *entities* against *query*.

    Returns up to *max_results* entities sorted by descending relevance.
    Entities with a score of zero are excluded.

    When *usage_stats* is provided, a usage boost is added to the fuzzy
    score to prefer recently and frequently used entities.  An empty
    *query* returns entities sorted by usage score (most-used first),
    falling back to alphabetical order for entities with no usage history.
    """
    query = query.strip()
    ts = now if now is not None else time.time()

    if not query:
        if usage_stats:
            # Sort by usage score descending, then alphabetically
            return sorted(
                entities,
                key=lambda e: (
                    -_usage_score(e.entity_id, usage_stats, ts),
                    e.friendly_name.lower(),
                ),
            )[:max_results]
        return entities[:max_results]

    scored: list[tuple[float, int, Entity]] = []
    for idx, entity in enumerate(entities):
        s = _score_entity_multi(entity, query)
        if s > 0:
            if usage_stats:
                s += _usage_score(entity.entity_id, usage_stats, ts)
            scored.append((s, idx, entity))

    # Sort by score descending, then original order for stability
    scored.sort(key=lambda x: (-x[0], x[1]))

    return [entity for _, _, entity in scored[:max_results]]
