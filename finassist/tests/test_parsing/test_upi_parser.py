from __future__ import annotations

from core.parsing.upi_parser import parse_upi_narration


def test_upi_hdfc() -> None:
    result = parse_upi_narration("UPI-XXXXXX0315-ICIC0007236-128994831651-")
    assert result is not None
    assert result.method == "UPI"
    assert result.counterparty_ifsc == "ICIC0007236"
    assert result.reference_number == "128994831651"


def test_imps_hdfc() -> None:
    result = parse_upi_narration("IMPS-128713626494-NEXTBILLION TECHNOLO-Y")
    assert result is not None
    assert result.method == "IMPS"
    assert result.reference_number == "128713626494"
    assert result.counterparty_name == "NEXTBILLION TECHNOLO"


def test_vpa_present() -> None:
    result = parse_upi_narration("UPI-johndoe@okicici-1234-")
    assert result is not None
    assert result.counterparty_vpa == "johndoe@okicici"


def test_non_payment_returns_none() -> None:
    assert parse_upi_narration("ATW-XXXXX-NS BLR") is None


def test_empty_returns_none() -> None:
    assert parse_upi_narration("") is None


def test_neft_recognized() -> None:
    result = parse_upi_narration("NEFT-EMP12345-COMPANY NAME-HDFC0000123-SAL")
    assert result is not None
    assert result.method == "NEFT"
