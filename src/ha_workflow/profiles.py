"""Server profiles — which Home Assistant servers the workflow knows about.

There are two kinds of profile:

* The **default** profile comes from Alfred's workflow configuration
  (``HA_URL`` / ``HA_TOKEN``), exactly as before profiles existed.
* **Additional** profiles live in ``<alfred_workflow_data>/profiles.json``.
  That file never holds a secret: each profile's token lives in the login
  Keychain (see :mod:`keychain`), keyed by the profile id.

``profiles.json`` (schema v1)::

    {
      "schema_version": 1,
      "default": {"name": "Home", "badge": "HOME"},      # optional display overrides
      "profiles": [
        {"id": "p-1a2b3c4d", "name": "Lake House",
         "urls": ["https://lake.example.net"], "token_source": "keychain",
         "preferred_label": null, "badge": null}
      ]
    }

Unknown keys (top-level and per profile) are preserved on rewrite, so a newer
build's fields survive an older build's write.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Optional

from ha_workflow.config import normalize_server_url, server_key_for_url
from ha_workflow.errors import ConfigError

SCHEMA_VERSION = 1
DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Default"
PROFILES_FILENAME = "profiles.json"
TOKEN_SOURCE_ENV = "env"
TOKEN_SOURCE_KEYCHAIN = "keychain"

_PROFILE_ID_RE = re.compile(r"^p-[0-9a-f]{8}$")
_MAX_NAME_LEN = 64
_MAX_BADGE_LEN = 12
_KNOWN_PROFILE_KEYS = frozenset(
    {"id", "name", "urls", "token_source", "preferred_label", "badge"}
)
_KNOWN_TOP_KEYS = frozenset({"schema_version", "default", "profiles"})


class ProfilesFileError(ConfigError):
    """``profiles.json`` is unreadable or fails validation."""


@dataclass(frozen=True)
class Profile:
    """One Home Assistant server the workflow can talk to."""

    id: str
    name: str
    urls: tuple[str, ...]
    token_source: str
    preferred_label: Optional[str] = None
    badge: Optional[str] = None
    # Unknown keys read from profiles.json, written back untouched.
    extra: Mapping[str, Any] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )

    @property
    def is_default(self) -> bool:
        return self.id == DEFAULT_PROFILE_ID

    @property
    def url(self) -> str:
        """Primary URL (v1 profiles have exactly one)."""
        return self.urls[0]

    @property
    def host(self) -> str:
        """``host[:port][/path]`` of the primary URL, for display."""
        return normalize_server_url(self.url).split("://", 1)[-1]

    @property
    def storage_key(self) -> str:
        """Per-server storage key.

        The default profile keeps the URL-hash key (so existing storage stays
        valid); every other profile is keyed by its id, which never changes
        when its URL is edited.
        """
        if self.is_default:
            return server_key_for_url(self.url)
        return self.id

    @property
    def display_prefix(self) -> str:
        """Short label for subtitles and notifications: badge, else name."""
        return self.badge or self.name

    def to_dict(self) -> dict[str, Any]:
        """Serialize for ``profiles.json`` (never includes a token)."""
        data: dict[str, Any] = dict(self.extra)
        data.update(
            {
                "id": self.id,
                "name": self.name,
                "urls": list(self.urls),
                "token_source": self.token_source,
                "preferred_label": self.preferred_label,
                "badge": self.badge,
            }
        )
        return data


@dataclass(frozen=True)
class ProfilesFile:
    """Parsed contents of ``profiles.json``."""

    profiles: tuple[Profile, ...] = ()
    default_name: Optional[str] = None
    default_badge: Optional[str] = None
    extra: Mapping[str, Any] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )
    default_extra: Mapping[str, Any] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )

    def get(self, profile_id: str) -> Optional[Profile]:
        for prof in self.profiles:
            if prof.id == profile_id:
                return prof
        return None

    def with_profile(self, profile: Profile) -> ProfilesFile:
        """Return a copy with *profile* appended (validated for uniqueness)."""
        updated = replace(self, profiles=(*self.profiles, profile))
        _check_unique(updated.profiles)
        return updated

    def replacing(self, profile: Profile) -> ProfilesFile:
        """Return a copy with the profile of the same id replaced."""
        profs = tuple(profile if p.id == profile.id else p for p in self.profiles)
        updated = replace(self, profiles=profs)
        _check_unique(updated.profiles)
        return updated

    def without_profile(self, profile_id: str) -> ProfilesFile:
        return replace(
            self, profiles=tuple(p for p in self.profiles if p.id != profile_id)
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.extra)
        data["schema_version"] = SCHEMA_VERSION
        default: dict[str, Any] = dict(self.default_extra)
        if self.default_name is not None:
            default["name"] = self.default_name
        if self.default_badge is not None:
            default["badge"] = self.default_badge
        if default:
            data["default"] = default
        data["profiles"] = [p.to_dict() for p in self.profiles]
        return data


@dataclass(frozen=True)
class ServerList:
    """Every configured server, resolved without raising.

    Used where an invalid ``profiles.json`` must not hide the default server
    (the ``server:`` listing).  ``file_error`` carries the reason.
    """

    profiles: tuple[Profile, ...]
    file: Optional[ProfilesFile]
    file_error: Optional[str]
    file_exists: bool

    def get(self, profile_id: str) -> Optional[Profile]:
        for prof in self.profiles:
            if prof.id == profile_id:
                return prof
        return None


# ---------------------------------------------------------------------------
# Ids
# ---------------------------------------------------------------------------


def is_valid_profile_id(value: str) -> bool:
    """True for ``p-<8 lowercase hex>`` — the only id a stored profile may have."""
    return bool(_PROFILE_ID_RE.match(value))


def new_profile_id() -> str:
    """Random, stable id for a new profile."""
    return "p-" + secrets.token_hex(4)


# ---------------------------------------------------------------------------
# Parsing / validation
# ---------------------------------------------------------------------------


def _clean_str(value: Any, what: str, max_len: int, required: bool) -> Optional[str]:
    if value is None:
        if required:
            raise ProfilesFileError(f"{what} is required")
        return None
    if not isinstance(value, str):
        raise ProfilesFileError(f"{what} must be a string")
    text = value.strip()
    if not text:
        if required:
            raise ProfilesFileError(f"{what} must not be empty")
        return None
    if len(text) > max_len:
        raise ProfilesFileError(f"{what} is longer than {max_len} characters")
    if any(ord(c) < 32 for c in text):
        raise ProfilesFileError(f"{what} contains control characters")
    return text


def validate_url(url: Any) -> str:
    """Return *url* stripped of whitespace and trailing ``/``, or raise."""
    if not isinstance(url, str) or not url.strip():
        raise ProfilesFileError("URL must be a non-empty string")
    text = url.strip()
    lowered = text.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ProfilesFileError(f"URL {text!r} must start with http:// or https://")
    host = normalize_server_url(text).split("://", 1)[-1]
    if not host or host.startswith("/"):
        raise ProfilesFileError(f"URL {text!r} has no host")
    return text.rstrip("/")


def validate_name(name: Any) -> str:
    cleaned = _clean_str(name, "name", _MAX_NAME_LEN, required=True)
    assert cleaned is not None
    return cleaned


def validate_badge(badge: Any) -> Optional[str]:
    return _clean_str(badge, "badge", _MAX_BADGE_LEN, required=False)


def parse_profile(entry: Any) -> Profile:
    """Validate one ``profiles.json`` entry and build a :class:`Profile`."""
    if not isinstance(entry, dict):
        raise ProfilesFileError("each profile must be an object")
    pid = entry.get("id")
    if not isinstance(pid, str) or not is_valid_profile_id(pid):
        raise ProfilesFileError(
            f"profile id {pid!r} is invalid (expected 'p-' followed by 8 hex digits)"
        )
    name = validate_name(entry.get("name"))
    urls_raw = entry.get("urls")
    if not isinstance(urls_raw, list) or len(urls_raw) != 1:
        raise ProfilesFileError(f"profile {name!r} needs exactly one URL in 'urls'")
    urls = (validate_url(urls_raw[0]),)
    token_source = entry.get("token_source", TOKEN_SOURCE_KEYCHAIN)
    if token_source != TOKEN_SOURCE_KEYCHAIN:
        raise ProfilesFileError(
            f"profile {name!r}: token_source must be 'keychain', got {token_source!r}"
        )
    label = _clean_str(entry.get("preferred_label"), "preferred_label", 255, False)
    badge = validate_badge(entry.get("badge"))
    extra = {k: v for k, v in entry.items() if k not in _KNOWN_PROFILE_KEYS}
    return Profile(
        id=pid,
        name=name,
        urls=urls,
        token_source=TOKEN_SOURCE_KEYCHAIN,
        preferred_label=label.lower() if label else None,
        badge=badge,
        extra=extra,
    )


def _check_unique(profiles: tuple[Profile, ...]) -> None:
    seen_ids: set[str] = set()
    seen_names: dict[str, str] = {}
    seen_urls: dict[str, str] = {}
    for prof in profiles:
        if prof.id in seen_ids:
            raise ProfilesFileError(f"duplicate profile id {prof.id!r}")
        seen_ids.add(prof.id)
        key = prof.name.casefold()
        if key in seen_names:
            raise ProfilesFileError(
                f"duplicate server name {prof.name!r} (names must be unique)"
            )
        seen_names[key] = prof.name
        norm = normalize_server_url(prof.url)
        if norm in seen_urls:
            raise ProfilesFileError(
                f"servers {seen_urls[norm]!r} and {prof.name!r} have the same URL"
            )
        seen_urls[norm] = prof.name


def parse_profiles_data(data: Any) -> ProfilesFile:
    """Validate the decoded JSON of ``profiles.json``."""
    if not isinstance(data, dict):
        raise ProfilesFileError("top level must be a JSON object")
    version = data.get("schema_version", SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ProfilesFileError("schema_version must be an integer")
    if version > SCHEMA_VERSION:
        raise ProfilesFileError(
            f"schema_version {version} was written by a newer version of the workflow"
        )
    raw_profiles = data.get("profiles", [])
    if not isinstance(raw_profiles, list):
        raise ProfilesFileError("'profiles' must be a list")
    profiles = tuple(parse_profile(entry) for entry in raw_profiles)
    _check_unique(profiles)

    default_raw = data.get("default", {})
    if not isinstance(default_raw, dict):
        raise ProfilesFileError("'default' must be an object")
    default_name = _clean_str(
        default_raw.get("name"), "default name", _MAX_NAME_LEN, False
    )
    default_badge = validate_badge(default_raw.get("badge"))
    return ProfilesFile(
        profiles=profiles,
        default_name=default_name,
        default_badge=default_badge,
        extra={k: v for k, v in data.items() if k not in _KNOWN_TOP_KEYS},
        default_extra={
            k: v for k, v in default_raw.items() if k not in ("name", "badge")
        },
    )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def profiles_path(data_dir: Path) -> Path:
    return Path(data_dir) / PROFILES_FILENAME


def load_profiles_file(data_dir: Path) -> Optional[ProfilesFile]:
    """Read ``profiles.json``; ``None`` when it does not exist."""
    path = profiles_path(data_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProfilesFileError(f"cannot read {path.name}: {exc}") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ProfilesFileError(f"not valid JSON ({exc})") from exc
    return parse_profiles_data(data)


def atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* via a temp file + :func:`os.replace`."""
    os.makedirs(path.parent, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def save_profiles_file(data_dir: Path, profiles_file: ProfilesFile) -> None:
    """Atomically write ``profiles.json``."""
    text = json.dumps(profiles_file.to_dict(), indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(profiles_path(data_dir), text)


# ---------------------------------------------------------------------------
# Default profile + combined view
# ---------------------------------------------------------------------------


def default_profile_from_env(
    env: Mapping[str, str], profiles_file: Optional[ProfilesFile] = None
) -> Optional[Profile]:
    """The implicit profile backed by ``HA_URL`` / ``HA_TOKEN``, if configured."""
    ha_url = env.get("HA_URL", "").strip().rstrip("/")
    if not ha_url:
        return None
    name = DEFAULT_PROFILE_NAME
    badge: Optional[str] = None
    if profiles_file is not None:
        name = profiles_file.default_name or name
        badge = profiles_file.default_badge
    return Profile(
        id=DEFAULT_PROFILE_ID,
        name=name,
        urls=(ha_url,),
        token_source=TOKEN_SOURCE_ENV,
        badge=badge,
    )


def load_servers(env: Mapping[str, str], data_dir: Path) -> ServerList:
    """Default profile (if configured) followed by the valid file profiles.

    Never raises for a bad ``profiles.json``: the error is reported in
    ``file_error`` and only the default profile is returned.
    """
    file_exists = profiles_path(data_dir).exists()
    profiles_file: Optional[ProfilesFile] = None
    file_error: Optional[str] = None
    try:
        profiles_file = load_profiles_file(data_dir)
    except ProfilesFileError as exc:
        file_error = str(exc)

    default = default_profile_from_env(env, profiles_file)
    profiles: tuple[Profile, ...] = (default,) if default else ()
    if profiles_file is not None:
        combined = profiles + profiles_file.profiles
        try:
            _check_unique(combined)
        except ProfilesFileError as exc:
            file_error = str(exc)
            profiles_file = None
            default = default_profile_from_env(env, None)
            profiles = (default,) if default else ()
        else:
            profiles = combined
    return ServerList(
        profiles=profiles,
        file=profiles_file,
        file_error=file_error,
        file_exists=file_exists,
    )
