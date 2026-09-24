"""Tests for server profiles: model, profiles.json loader/writer, validation.

Every test runs against both copies of the library code — ``ha_workflow``
(used by ``cli.py``) and ``ha_lib`` (used by the Alfred scripts).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_PACKAGES = ["ha_workflow", "ha_lib"]


class _Lib:
    def __init__(self, package: str) -> None:
        self.package = package
        self.profiles: ModuleType = importlib.import_module(f"{package}.profiles")
        self.config: ModuleType = importlib.import_module(f"{package}.config")
        self.errors: ModuleType = importlib.import_module(f"{package}.errors")


@pytest.fixture(params=_PACKAGES)
def lib(request: pytest.FixtureRequest) -> _Lib:
    return _Lib(request.param)


def _write(data_dir: Path, payload: Any) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "profiles.json"
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text)
    return path


def _lake(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "p-1a2b3c4d",
        "name": "Lake House",
        "urls": ["https://lake.example.net"],
        "token_source": "keychain",
    }
    entry.update(overrides)
    return entry


_ENV = {"HA_URL": "http://ha.local:8123", "HA_TOKEN": "tok"}


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------


class TestProfileModel:
    def test_default_profile_from_env(self, lib: _Lib) -> None:
        prof = lib.profiles.default_profile_from_env(_ENV)
        assert prof.id == "default"
        assert prof.is_default
        assert prof.token_source == "env"
        assert prof.urls == ("http://ha.local:8123",)
        assert prof.name == "Default"

    def test_default_profile_absent_without_url(self, lib: _Lib) -> None:
        assert lib.profiles.default_profile_from_env({}) is None

    def test_default_storage_key_is_url_hash(self, lib: _Lib) -> None:
        prof = lib.profiles.default_profile_from_env(_ENV)
        assert prof.storage_key == lib.config.server_key_for_url(_ENV["HA_URL"])

    def test_keychain_storage_key_is_id_and_ignores_url(self, lib: _Lib) -> None:
        a = lib.profiles.parse_profile(_lake())
        b = lib.profiles.parse_profile(_lake(urls=["https://other.example.net"]))
        assert a.storage_key == "p-1a2b3c4d"
        assert b.storage_key == a.storage_key

    def test_host_and_prefix(self, lib: _Lib) -> None:
        prof = lib.profiles.parse_profile(_lake(badge="LAKE"))
        assert prof.host == "lake.example.net"
        assert prof.display_prefix == "LAKE"
        plain = lib.profiles.parse_profile(_lake())
        assert plain.display_prefix == "Lake House"

    def test_new_profile_id_format(self, lib: _Lib) -> None:
        ids = {lib.profiles.new_profile_id() for _ in range(50)}
        assert len(ids) == 50
        assert all(lib.profiles.is_valid_profile_id(i) for i in ids)

    @pytest.mark.parametrize(
        ("value", "ok"),
        [
            ("p-1a2b3c4d", True),
            ("default", False),
            ("p-1A2B3C4D", False),
            ("p-1a2b3c4", False),
            ("p-1a2b3c4d0", False),
            ("../p-1a2b3c4d", False),
            ("", False),
        ],
    )
    def test_profile_id_validation(self, lib: _Lib, value: str, ok: bool) -> None:
        assert lib.profiles.is_valid_profile_id(value) is ok

    def test_profile_ids_pass_server_key_seam(self, lib: _Lib, tmp_path: Path) -> None:
        """A ``p-<8hex>`` id must be accepted by Config's server-key validation."""
        pid = lib.profiles.new_profile_id()
        cfg = lib.config.Config(
            ha_url="https://lake.example.net",
            ha_token="t",
            cache_ttl=60,
            cache_dir=tmp_path / "c",
            data_dir=tmp_path / "d",
            server_key_override=pid,
        )
        assert cfg.server_key == pid


# ---------------------------------------------------------------------------
# profiles.json loader
# ---------------------------------------------------------------------------


class TestLoadProfilesFile:
    def test_absent_file_is_none(self, lib: _Lib, tmp_path: Path) -> None:
        assert lib.profiles.load_profiles_file(tmp_path) is None

    def test_valid_file(self, lib: _Lib, tmp_path: Path) -> None:
        _write(tmp_path, {"schema_version": 1, "profiles": [_lake(badge="🏠")]})
        pf = lib.profiles.load_profiles_file(tmp_path)
        assert pf is not None
        assert [p.id for p in pf.profiles] == ["p-1a2b3c4d"]
        assert pf.profiles[0].badge == "🏠"
        assert pf.profiles[0].token_source == "keychain"

    def test_token_source_defaults_to_keychain(self, lib: _Lib, tmp_path: Path) -> None:
        entry = _lake()
        del entry["token_source"]
        _write(tmp_path, {"schema_version": 1, "profiles": [entry]})
        pf = lib.profiles.load_profiles_file(tmp_path)
        assert pf is not None
        assert pf.profiles[0].token_source == "keychain"

    def test_preferred_label_lowercased(self, lib: _Lib, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {"schema_version": 1, "profiles": [_lake(preferred_label=" Lake_Fav ")]},
        )
        pf = lib.profiles.load_profiles_file(tmp_path)
        assert pf is not None
        assert pf.profiles[0].preferred_label == "lake_fav"

    def test_default_display_overrides(self, lib: _Lib, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {
                "schema_version": 1,
                "default": {"name": "Home", "badge": "HOME"},
                "profiles": [],
            },
        )
        pf = lib.profiles.load_profiles_file(tmp_path)
        assert pf is not None
        prof = lib.profiles.default_profile_from_env(_ENV, pf)
        assert prof.name == "Home"
        assert prof.badge == "HOME"
        assert prof.display_prefix == "HOME"

    @pytest.mark.parametrize(
        ("payload", "reason"),
        [
            ("{not json", "JSON"),
            ([], "object"),
            ({"schema_version": 1, "profiles": {}}, "list"),
            ({"schema_version": 99, "profiles": []}, "newer"),
            ({"schema_version": "1", "profiles": []}, "schema_version"),
            ({"schema_version": 1, "profiles": ["x"]}, "object"),
            ({"schema_version": 1, "profiles": [_lake(id="default")]}, "id"),
            ({"schema_version": 1, "profiles": [_lake(id="../x")]}, "id"),
            ({"schema_version": 1, "profiles": [_lake(name="  ")]}, "name"),
            ({"schema_version": 1, "profiles": [_lake(urls=[])]}, "URL"),
            (
                {"schema_version": 1, "profiles": [_lake(urls=["a", "b"])]},
                "URL",
            ),
            ({"schema_version": 1, "profiles": [_lake(urls=["ftp://x"])]}, "http"),
            ({"schema_version": 1, "profiles": [_lake(urls=["https://"])]}, "host"),
            (
                {"schema_version": 1, "profiles": [_lake(token_source="env")]},
                "token_source",
            ),
            ({"schema_version": 1, "profiles": [_lake(badge="x" * 40)]}, "badge"),
            ({"schema_version": 1, "profiles": [_lake(name=5)]}, "name"),
        ],
    )
    def test_invalid_file(
        self, lib: _Lib, tmp_path: Path, payload: Any, reason: str
    ) -> None:
        _write(tmp_path, payload)
        with pytest.raises(lib.profiles.ProfilesFileError, match=reason):
            lib.profiles.load_profiles_file(tmp_path)

    def test_profiles_file_error_is_config_error(self, lib: _Lib) -> None:
        assert issubclass(lib.profiles.ProfilesFileError, lib.errors.ConfigError)

    def test_duplicate_name_case_insensitive(self, lib: _Lib, tmp_path: Path) -> None:
        second = _lake(id="p-00000000", name="LAKE house", urls=["https://b.example"])
        _write(tmp_path, {"schema_version": 1, "profiles": [_lake(), second]})
        with pytest.raises(lib.profiles.ProfilesFileError, match="name"):
            lib.profiles.load_profiles_file(tmp_path)

    def test_duplicate_url_after_normalization(self, lib: _Lib, tmp_path: Path) -> None:
        second = _lake(
            id="p-00000000", name="Other", urls=["HTTPS://Lake.Example.NET:443/"]
        )
        _write(tmp_path, {"schema_version": 1, "profiles": [_lake(), second]})
        with pytest.raises(lib.profiles.ProfilesFileError, match="URL"):
            lib.profiles.load_profiles_file(tmp_path)

    def test_duplicate_id(self, lib: _Lib, tmp_path: Path) -> None:
        second = _lake(name="Other", urls=["https://b.example"])
        _write(tmp_path, {"schema_version": 1, "profiles": [_lake(), second]})
        with pytest.raises(lib.profiles.ProfilesFileError, match="id"):
            lib.profiles.load_profiles_file(tmp_path)


# ---------------------------------------------------------------------------
# Writer — atomic, unknown keys preserved
# ---------------------------------------------------------------------------


class TestSaveProfilesFile:
    def test_round_trip(self, lib: _Lib, tmp_path: Path) -> None:
        prof = lib.profiles.parse_profile(_lake(badge="L"))
        pf = lib.profiles.ProfilesFile(profiles=(prof,))
        lib.profiles.save_profiles_file(tmp_path, pf)
        loaded = lib.profiles.load_profiles_file(tmp_path)
        assert loaded is not None
        assert loaded.profiles == (prof,)
        raw = json.loads((tmp_path / "profiles.json").read_text())
        assert raw["schema_version"] == 1

    def test_unknown_keys_preserved(self, lib: _Lib, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {
                "schema_version": 1,
                "future_top": {"x": 1},
                "profiles": [_lake(future_field="keep-me")],
            },
        )
        pf = lib.profiles.load_profiles_file(tmp_path)
        assert pf is not None
        extra = lib.profiles.parse_profile(
            _lake(id="p-00000000", name="Cabin", urls=["https://cabin.example"])
        )
        lib.profiles.save_profiles_file(tmp_path, pf.with_profile(extra))
        raw = json.loads((tmp_path / "profiles.json").read_text())
        assert raw["future_top"] == {"x": 1}
        assert raw["profiles"][0]["future_field"] == "keep-me"
        assert [p["id"] for p in raw["profiles"]] == ["p-1a2b3c4d", "p-00000000"]

    def test_never_writes_a_token(self, lib: _Lib, tmp_path: Path) -> None:
        prof = lib.profiles.parse_profile(_lake())
        lib.profiles.save_profiles_file(
            tmp_path, lib.profiles.ProfilesFile(profiles=(prof,))
        )
        text = (tmp_path / "profiles.json").read_text().lower()
        assert 'token"' not in text.replace("token_source", "")

    def test_atomic_write_leaves_no_temp_files(self, lib: _Lib, tmp_path: Path) -> None:
        prof = lib.profiles.parse_profile(_lake())
        lib.profiles.save_profiles_file(
            tmp_path, lib.profiles.ProfilesFile(profiles=(prof,))
        )
        assert sorted(p.name for p in tmp_path.iterdir()) == ["profiles.json"]

    def test_without_profile(self, lib: _Lib) -> None:
        prof = lib.profiles.parse_profile(_lake())
        pf = lib.profiles.ProfilesFile(profiles=(prof,))
        assert pf.without_profile("p-1a2b3c4d").profiles == ()

    def test_with_profile_rejects_duplicates(self, lib: _Lib) -> None:
        prof = lib.profiles.parse_profile(_lake())
        pf = lib.profiles.ProfilesFile(profiles=(prof,))
        dup = lib.profiles.parse_profile(
            _lake(id="p-00000000", urls=["https://x.example"])
        )
        with pytest.raises(lib.profiles.ProfilesFileError, match="name"):
            pf.with_profile(dup)


# ---------------------------------------------------------------------------
# load_servers — the non-throwing view used by the `server:` listing
# ---------------------------------------------------------------------------


class TestLoadServers:
    def test_default_only(self, lib: _Lib, tmp_path: Path) -> None:
        servers = lib.profiles.load_servers(_ENV, tmp_path)
        assert [p.id for p in servers.profiles] == ["default"]
        assert servers.file_error is None
        assert not servers.file_exists

    def test_default_plus_file(self, lib: _Lib, tmp_path: Path) -> None:
        _write(tmp_path, {"schema_version": 1, "profiles": [_lake()]})
        servers = lib.profiles.load_servers(_ENV, tmp_path)
        assert [p.id for p in servers.profiles] == ["default", "p-1a2b3c4d"]
        assert servers.get("p-1a2b3c4d") is not None
        assert servers.get("p-ffffffff") is None
        assert servers.file_exists

    def test_invalid_file_keeps_default(self, lib: _Lib, tmp_path: Path) -> None:
        _write(tmp_path, "{broken")
        servers = lib.profiles.load_servers(_ENV, tmp_path)
        assert [p.id for p in servers.profiles] == ["default"]
        assert servers.file_error is not None
        assert servers.file_exists

    def test_no_url_no_file(self, lib: _Lib, tmp_path: Path) -> None:
        servers = lib.profiles.load_servers({}, tmp_path)
        assert servers.profiles == ()

    def test_file_profile_duplicating_default_url_is_invalid(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        _write(
            tmp_path,
            {"schema_version": 1, "profiles": [_lake(urls=["http://HA.local:8123/"])]},
        )
        servers = lib.profiles.load_servers(_ENV, tmp_path)
        assert servers.file_error is not None
        assert "URL" in servers.file_error
        assert [p.id for p in servers.profiles] == ["default"]
