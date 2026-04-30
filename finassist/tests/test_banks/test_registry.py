from __future__ import annotations

from core.banks.registry import detect_bank, get_adapter_by_code


def test_detect_hdfc_csv(hdfc_csv_simple) -> None:
    adapter = detect_bank(hdfc_csv_simple)
    assert adapter is not None
    assert adapter.bank_code == "HDFC"


def test_detect_unknown_returns_none(tmp_path) -> None:
    p = tmp_path / "unknown.csv"
    p.write_text("foo,bar\n1,2\n")
    assert detect_bank(p) is None


def test_get_adapter_by_code() -> None:
    assert get_adapter_by_code("HDFC") is not None
    assert get_adapter_by_code("SBI") is None
