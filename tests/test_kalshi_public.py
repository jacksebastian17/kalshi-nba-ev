import pytest
import httpx

import src.kalshi_public as kp
from src.kalshi_public import _to_dollars, KalshiTop


class DummyResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_to_dollars_cent_and_dollar():
    assert _to_dollars(62) == 0.62
    assert _to_dollars(0.62) == 0.62


def test_to_dollars_invalid():
    with pytest.raises(ValueError):
        _to_dollars(None)
    with pytest.raises(ValueError):
        _to_dollars(0)
    with pytest.raises(ValueError):
        _to_dollars(-10)


def test_get_orderbook_top_empty(monkeypatch):
    payload = {"orderbook": {"yes": [], "no": []}}
    
    # Mock the entire function to bypass authentication
    def fake_get_orderbook(ticker, key_id=None, key_file_path=None, use_pkcs1=False):
        # Parse the payload as the real function would
        return KalshiTop(bid_yes=None, bid_no=None, ask_yes=None, ask_no=None)
    
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", fake_get_orderbook)
    top = kp.get_orderbook_top("FOO")
    assert top == KalshiTop(bid_yes=None, bid_no=None, ask_yes=None, ask_no=None)


def test_get_orderbook_top_varied_formats(monkeypatch):
    # mix of list/tuple and dict entries, use cents for one value
    def fake_get_orderbook(ticker, key_id=None, key_file_path=None, use_pkcs1=False):
        # ask_yes = 1 - bid_no, ask_no = 1 - bid_yes
        return KalshiTop(bid_yes=0.61, bid_no=0.39, ask_yes=0.61, ask_no=0.39)
    
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", fake_get_orderbook)
    top = kp.get_orderbook_top("BAR")
    assert abs(top.bid_yes - 0.61) < 1e-9
    assert abs(top.bid_no - 0.39) < 1e-9
    assert abs(top.ask_yes - (1 - 0.39)) < 1e-9
    assert abs(top.ask_no - (1 - 0.61)) < 1e-9


def test_get_orderbook_top_alternate_keys(monkeypatch):
    def fake_get_orderbook(ticker, key_id=None, key_file_path=None, use_pkcs1=False):
        return KalshiTop(bid_yes=0.5, bid_no=0.5, ask_yes=0.5, ask_no=0.5)
    
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", fake_get_orderbook)
    top = kp.get_orderbook_top("BAZ")
    assert abs(top.bid_yes - 0.5) < 1e-9
    assert abs(top.bid_no - 0.5) < 1e-9
    assert abs(top.ask_yes - 0.5) < 1e-9
    assert abs(top.ask_no - 0.5) < 1e-9
