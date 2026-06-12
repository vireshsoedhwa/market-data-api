from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.validation import validate_batch_symbols, validate_date_range, validate_symbol


class TestValidateSymbol:
    def test_valid_symbol(self):
        assert validate_symbol("AAPL") == "AAPL"

    def test_lowercased_is_uppercased(self):
        assert validate_symbol("aapl") == "AAPL"

    def test_symbol_with_dot(self):
        assert validate_symbol("BRK.B") == "BRK.B"

    def test_symbol_with_hyphen(self):
        assert validate_symbol("RY-T") == "RY-T"

    def test_numeric_symbol(self):
        assert validate_symbol("7203") == "7203"

    def test_empty_string_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_symbol("")
        assert exc_info.value.status_code == 400

    def test_too_long_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_symbol("AAAAAAAAAAAA")
        assert exc_info.value.status_code == 400

    def test_special_chars_raise(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_symbol("BAD!!!")
        assert exc_info.value.status_code == 400

    def test_spaces_raise(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_symbol("A B")
        assert exc_info.value.status_code == 400


class TestValidateDateRange:
    def test_valid_range(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        assert validate_date_range(start, end) == (start, end)

    def test_same_date_is_valid(self):
        d = date(2024, 6, 1)
        assert validate_date_range(d, d) == (d, d)

    def test_start_after_end_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(date(2024, 12, 31), date(2024, 1, 1))
        assert exc_info.value.status_code == 400

    def test_far_future_end_date_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(date(2024, 1, 1), date(2099, 1, 1))
        assert exc_info.value.status_code == 400

    def test_tomorrow_is_allowed(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        assert validate_date_range(today, tomorrow) == (today, tomorrow)


class TestValidateBatchSymbols:
    def test_valid_batch(self):
        result = validate_batch_symbols(["AAPL", "nvda", "MSFT"])
        assert result == ["AAPL", "NVDA", "MSFT"]

    def test_empty_batch(self):
        assert validate_batch_symbols([]) == []

    def test_too_large_raises(self):
        symbols = [f"SYM{i}" for i in range(51)]
        with pytest.raises(HTTPException) as exc_info:
            validate_batch_symbols(symbols)
        assert exc_info.value.status_code == 400

    def test_invalid_symbol_in_batch_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_batch_symbols(["AAPL", "BAD!!!"])
        assert exc_info.value.status_code == 400
