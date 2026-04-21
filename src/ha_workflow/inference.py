"""Infer the HA service (action) to call for a given domain + user-supplied params.

Used by the quick-exec flow where the user types
``<entity_id> <param_str>`` and expects the workflow to figure out the
right service (e.g. ``light.turn_on`` when they supply brightness/color).
"""

from __future__ import annotations

from collections.abc import Iterable

from ha_workflow.entities import ACTION_PARAMS, get_domain_config


def infer_action(domain: str, param_keys: Iterable[str]) -> str:
    """Pick the best-matching action in *domain* for the supplied *param_keys*.

    Rules:

    1. No params supplied → the domain's default action
       (e.g. ``light`` → ``toggle``).
    2. Else, score every parameterized action registered for *domain* by
       the number of user-supplied keys it declares.  The strict winner is
       returned.
    3. On a tie (or when nothing matches), fall back to the default action.
    4. Unknown domain with no default → ``""``.

    The returned string is always safe to pass to ``dispatch_action`` — it's
    either a valid action for the domain or an empty string that the
    dispatcher will reject with a clear error.
    """
    keys = {k for k in param_keys if k}
    default = get_domain_config(domain).default_action

    if not keys:
        return default

    candidates = [
        (action, set(p.name for p in params))
        for (dom, action), params in ACTION_PARAMS.items()
        if dom == domain
    ]
    if not candidates:
        return default

    scored = [(len(keys & declared), action) for action, declared in candidates]
    scored.sort(key=lambda t: (-t[0], t[1]))  # highest score, then alpha for stability

    top_score = scored[0][0]
    if top_score == 0:
        return default
    # Strict winner only — avoid guessing on ties (e.g. cover.open_cover vs
    # cover.close_cover both take ``position``).
    if len(scored) > 1 and scored[1][0] == top_score:
        return default

    return scored[0][1]
