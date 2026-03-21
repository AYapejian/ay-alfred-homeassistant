"""Tests for ha_workflow.usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from ha_workflow.config import Config
from ha_workflow.usage import UsageRecord, UsageTracker, open_usage_tracker


def _mem_tracker() -> UsageTracker:
    return UsageTracker(":memory:")


class TestSchema:
    def test_table_created(self) -> None:
        tracker = _mem_tracker()
        cur = tracker._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        assert "usage_stats" in tables
        tracker.close()

    def test_idempotent_schema_creation(self) -> None:
        tracker = _mem_tracker()
        # Call _init_schema again — should not raise
        tracker._init_schema()
        tracker.close()


class TestRecordUsage:
    def test_first_record(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.kitchen")
        record = tracker.get_usage_record("light.kitchen")
        assert record is not None
        assert record.entity_id == "light.kitchen"
        assert record.use_count == 1
        assert record.last_used_at > 0
        tracker.close()

    def test_increment_count(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.kitchen")
        tracker.record_usage("light.kitchen")
        tracker.record_usage("light.kitchen")
        record = tracker.get_usage_record("light.kitchen")
        assert record is not None
        assert record.use_count == 3
        tracker.close()

    @patch("ha_workflow.usage.time.time")
    def test_updates_last_used_at(self, mock_time: Any) -> None:
        tracker = _mem_tracker()
        mock_time.return_value = 1000.0
        tracker.record_usage("light.kitchen")
        mock_time.return_value = 2000.0
        tracker.record_usage("light.kitchen")
        record = tracker.get_usage_record("light.kitchen")
        assert record is not None
        assert record.last_used_at == 2000.0
        tracker.close()

    def test_multiple_entities(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.kitchen")
        tracker.record_usage("switch.fan")
        tracker.record_usage("light.kitchen")
        stats = tracker.get_usage_stats()
        assert len(stats) == 2
        assert stats["light.kitchen"].use_count == 2
        assert stats["switch.fan"].use_count == 1
        tracker.close()


class TestGetUsageStats:
    def test_empty_returns_empty_dict(self) -> None:
        tracker = _mem_tracker()
        assert tracker.get_usage_stats() == {}
        tracker.close()

    def test_returns_all_records(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("a.one")
        tracker.record_usage("b.two")
        stats = tracker.get_usage_stats()
        assert set(stats.keys()) == {"a.one", "b.two"}
        tracker.close()


class TestCountAndClear:
    def test_count_empty(self) -> None:
        tracker = _mem_tracker()
        assert tracker.count() == 0
        tracker.close()

    def test_count_after_records(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.a")
        tracker.record_usage("light.b")
        tracker.record_usage("light.a")  # increment, not new
        assert tracker.count() == 2
        tracker.close()

    def test_clear_removes_all(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.a")
        tracker.record_usage("light.b")
        tracker.clear()
        assert tracker.count() == 0
        assert tracker.get_usage_stats() == {}
        tracker.close()

    def test_clear_on_empty_is_safe(self) -> None:
        tracker = _mem_tracker()
        tracker.clear()  # should not raise
        assert tracker.count() == 0
        tracker.close()


class TestGetUsageRecord:
    def test_unknown_entity_returns_none(self) -> None:
        tracker = _mem_tracker()
        assert tracker.get_usage_record("nonexistent.entity") is None
        tracker.close()

    def test_returns_correct_record(self) -> None:
        tracker = _mem_tracker()
        tracker.record_usage("light.bedroom")
        record = tracker.get_usage_record("light.bedroom")
        assert isinstance(record, UsageRecord)
        assert record.entity_id == "light.bedroom"
        tracker.close()


class TestOpenUsageTracker:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        config = Config(
            ha_url="http://ha.local:8123",
            ha_token="test-token",
            cache_ttl=60,
            cache_dir=tmp_path / "cache",
            data_dir=tmp_path / "data",
        )
        tracker = open_usage_tracker(config)
        db_file = tmp_path / "data" / "usage.db"
        assert db_file.exists()
        tracker.close()
