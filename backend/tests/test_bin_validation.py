"""Unit tests for Kazakhstan BIN checksum validator.

Known-good BINs used in tests:
  "190540000014" — year=19, month=05, entity=4 (resident legal entity),
                   unit=0 (head), seq=00001, check=4
                   Computed: sum([1*1,9*2,0*3,5*4,4*5,0*6,0*7,0*8,0*9,0*10,1*11])
                             = 1+18+0+20+20+0+0+0+0+0+11 = 70; 70%11 = 4. Check digit 4. ✓
  "190640000018" — year=19, month=06, entity=4, unit=0, seq=00001, check=8 ✓
"""
import pytest

from app.services.bin_validator import validate_bin


def test_valid_bin_resident_legal_entity() -> None:
    # "190540000014": entity type 4, check digit 4 verified by REPL
    assert validate_bin("190540000014") is True


def test_valid_bin_second_known_good() -> None:
    # "190640000018": entity type 4, check digit 8 verified by REPL
    assert validate_bin("190640000018") is True


def test_empty_string_returns_false() -> None:
    assert validate_bin("") is False


def test_too_short_returns_false() -> None:
    assert validate_bin("12345") is False


def test_too_long_returns_false() -> None:
    assert validate_bin("1905400000140") is False


def test_non_digit_char_returns_false() -> None:
    assert validate_bin("12345678901a") is False


def test_wrong_position_5_returns_false() -> None:
    # Position 5 (index 4) = '1' — individual IIN, not a legal-entity BIN
    assert validate_bin("190110100001") is False


def test_wrong_position_5_zero_returns_false() -> None:
    # Position 5 (index 4) = '0' — all-zeros BIN, not a legal entity
    assert validate_bin("000000000000") is False


def test_wrong_checksum_returns_false() -> None:
    # "190540000014" with last digit changed: intentionally bad checksum
    assert validate_bin("190540000019") is False


def test_non_digit_space_returns_false() -> None:
    assert validate_bin("190540 00014") is False
