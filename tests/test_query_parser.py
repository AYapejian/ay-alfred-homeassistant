"""Tests for ha_workflow.query_parser."""

from __future__ import annotations

from ha_workflow.query_parser import ParsedQuery, parse_query


class TestPlainFuzzy:
    def test_simple_text(self) -> None:
        result = parse_query("bedroom")
        assert result == ParsedQuery("fuzzy", "bedroom", None, None)

    def test_multi_word(self) -> None:
        result = parse_query("living room light")
        assert result == ParsedQuery("fuzzy", "living room light", None, None)

    def test_empty_string(self) -> None:
        result = parse_query("")
        assert result == ParsedQuery("fuzzy", "", None, None)

    def test_whitespace_only(self) -> None:
        result = parse_query("   ")
        assert result == ParsedQuery("fuzzy", "", None, None)

    def test_strips_whitespace(self) -> None:
        result = parse_query("  bedroom  ")
        assert result == ParsedQuery("fuzzy", "bedroom", None, None)


class TestDomainFilter:
    def test_domain_with_text(self) -> None:
        result = parse_query("light:bedroom")
        assert result.mode == "fuzzy"
        assert result.text == "bedroom"
        assert result.domain_filter == "light"
        assert result.regex_pattern is None

    def test_domain_with_text_and_space(self) -> None:
        result = parse_query("light: bedroom lamp")
        assert result.mode == "fuzzy"
        assert result.text == "bedroom lamp"
        assert result.domain_filter == "light"

    def test_bare_domain(self) -> None:
        result = parse_query("light:")
        assert result.mode == "domain_browse"
        assert result.text == ""
        assert result.domain_filter == "light"

    def test_underscored_domain(self) -> None:
        result = parse_query("binary_sensor:door")
        assert result.mode == "fuzzy"
        assert result.text == "door"
        assert result.domain_filter == "binary_sensor"

    def test_bare_underscored_domain(self) -> None:
        result = parse_query("input_boolean:")
        assert result.mode == "domain_browse"
        assert result.domain_filter == "input_boolean"

    def test_invalid_domain_falls_through(self) -> None:
        result = parse_query("zzz:foo")
        assert result.mode == "fuzzy"
        assert result.text == "zzz:foo"
        assert result.domain_filter is None

    def test_all_known_domains_accepted(self) -> None:
        from ha_workflow.entities import DOMAIN_REGISTRY

        for domain in DOMAIN_REGISTRY:
            result = parse_query(f"{domain}:test")
            assert result.domain_filter == domain, f"Failed for {domain}"

    def test_colon_in_middle_of_word_invalid_domain(self) -> None:
        result = parse_query("foo:bar")
        assert result.mode == "fuzzy"
        assert result.text == "foo:bar"
        assert result.domain_filter is None


class TestRegex:
    def test_basic_regex(self) -> None:
        result = parse_query("/bed.*room/")
        assert result.mode == "regex"
        assert result.regex_pattern == "bed.*room"
        assert result.text == ""
        assert result.domain_filter is None

    def test_anchored_regex(self) -> None:
        result = parse_query("/^light/")
        assert result.mode == "regex"
        assert result.regex_pattern == "^light"

    def test_single_slash_not_regex(self) -> None:
        result = parse_query("/")
        assert result.mode == "fuzzy"
        assert result.text == "/"

    def test_empty_regex(self) -> None:
        # "//" has pattern "" which is valid
        result = parse_query("//")
        assert result.mode == "regex"
        assert result.regex_pattern == ""

    def test_slash_in_text_not_regex(self) -> None:
        # Only one slash, not matching /pattern/
        result = parse_query("/foo")
        assert result.mode == "fuzzy"
        assert result.text == "/foo"

    def test_regex_with_special_chars(self) -> None:
        result = parse_query("/light\\.kit.*/")
        assert result.mode == "regex"
        assert result.regex_pattern == "light\\.kit.*"


class TestEdgeCases:
    def test_colon_only(self) -> None:
        result = parse_query(":")
        # ":" does not match domain prefix pattern (empty before colon)
        assert result.mode == "fuzzy"
        assert result.text == ":"

    def test_domain_like_but_with_spaces_before_colon(self) -> None:
        result = parse_query("light :bedroom")
        # Space before colon — not a domain filter
        assert result.mode == "fuzzy"
        assert result.text == "light :bedroom"
