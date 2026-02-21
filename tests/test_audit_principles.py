"""Tests for scripts/audit_principles.py."""

import ast
from pathlib import Path

from scripts.audit_principles import (
    check_raw_dict_events,
    check_raw_http,
    check_untyped_json_parse,
)


def _parse(code: str) -> ast.AST:
    return ast.parse(code)


class TestCheckRawHttp:
    def test_detects_requests_get(self):
        tree = _parse("import requests\nresult = requests.get('http://example.com')")
        violations = check_raw_http(Path("src/alpacalyzer/agents/foo.py"), tree)
        assert len(violations) == 1
        assert violations[0].rule == "NO-RAW-HTTP"

    def test_allows_trading_client(self):
        tree = _parse("import requests\nresult = requests.get('http://example.com')")
        violations = check_raw_http(Path("src/alpacalyzer/trading/alpaca_client.py"), tree)
        assert len(violations) == 0

    def test_allows_data_layer(self):
        tree = _parse("import requests\nresult = requests.get('http://example.com')")
        violations = check_raw_http(Path("src/alpacalyzer/data/api.py"), tree)
        assert len(violations) == 0

    def test_allows_scanners(self):
        tree = _parse("import requests\nresult = requests.get('http://example.com')")
        violations = check_raw_http(Path("src/alpacalyzer/scanners/stocktwits_scanner.py"), tree)
        assert len(violations) == 0

    def test_ignores_non_requests(self):
        tree = _parse("result = some_client.get('http://example.com')")
        violations = check_raw_http(Path("src/alpacalyzer/agents/foo.py"), tree)
        assert len(violations) == 0


class TestCheckRawDictEvents:
    def test_detects_dict_in_emit_event(self):
        tree = _parse("emit_event({'type': 'error', 'msg': 'bad'})")
        violations = check_raw_dict_events(Path("src/alpacalyzer/foo.py"), tree)
        assert len(violations) == 1
        assert violations[0].rule == "TYPED-EVENTS"

    def test_allows_typed_event(self):
        tree = _parse("emit_event(ErrorEvent(timestamp=now, error_type='x', component='y', message='z'))")
        violations = check_raw_dict_events(Path("src/alpacalyzer/foo.py"), tree)
        assert len(violations) == 0


class TestCheckUntypedJsonParse:
    def test_detects_raw_json_assignment(self):
        tree = _parse("data = response.json()")
        violations = check_untyped_json_parse(Path("src/alpacalyzer/agents/foo.py"), tree)
        assert len(violations) == 1
        assert violations[0].rule == "BOUNDARY-VALIDATION"

    def test_allows_in_test_files(self):
        tree = _parse("data = response.json()")
        violations = check_untyped_json_parse(Path("tests/test_foo.py"), tree)
        assert len(violations) == 0

    def test_allows_in_trading_client(self):
        tree = _parse("data = response.json()")
        violations = check_untyped_json_parse(Path("src/alpacalyzer/trading/alpaca_client.py"), tree)
        assert len(violations) == 0

    def test_allows_in_data_layer(self):
        tree = _parse("data = response.json()")
        violations = check_untyped_json_parse(Path("src/alpacalyzer/data/api.py"), tree)
        assert len(violations) == 0

    def test_allows_in_scanners(self):
        tree = _parse("data = response.json()")
        violations = check_untyped_json_parse(Path("src/alpacalyzer/scanners/wsb_scanner.py"), tree)
        assert len(violations) == 0
