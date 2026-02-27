import os
import pytest

import src.kalshi_public as kp
from src.kalshi_public import KalshiTop


class DummyResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_get_orderbook_top_includes_api_key_arg(monkeypatch):
    captured = {}

    def fake_get(url, timeout, headers=None):
        captured['url'] = url
        captured['headers'] = headers
        return DummyResponse({'orderbook': {'yes': [], 'no': []}})

    monkeypatch.setattr(kp.httpx, 'get', fake_get)
    # Mock _load_private_key to avoid file I/O
    monkeypatch.setattr(kp, '_load_private_key', lambda x: None)
    # Mock _sign_request to return a fake signature
    monkeypatch.setattr(kp, '_sign_request', lambda *args, **kwargs: 'fake_signature')
    
    kp.get_orderbook_top('XYZ', key_id='test_key_id', key_file_path='test.pem')
    assert captured['headers']['KALSHI-ACCESS-KEY'] == 'test_key_id'
    assert 'KALSHI-ACCESS-SIGNATURE' in captured['headers']


def test_get_orderbook_top_env_api_key(monkeypatch):
    # set environment variables via monkeypatch
    monkeypatch.setenv('KALSHI_KEY_ID', 'env_key_id')
    monkeypatch.setenv('KALSHI_KEY_FILE', 'env_test.pem')

    captured = {}

    def fake_get(url, timeout, headers=None, **kwargs):
        captured['headers'] = headers
        return DummyResponse({'orderbook': {'yes': [], 'no': []}})

    monkeypatch.setattr(kp.httpx, 'get', fake_get)
    # Mock _load_private_key to avoid file I/O
    monkeypatch.setattr(kp, '_load_private_key', lambda x: None)
    # Mock _sign_request to return a fake signature
    monkeypatch.setattr(kp, '_sign_request', lambda *args, **kwargs: 'fake_signature')
    
    kp.get_orderbook_top('ABC')
    assert captured['headers']['KALSHI-ACCESS-KEY'] == 'env_key_id'
    assert 'KALSHI-ACCESS-SIGNATURE' in captured['headers']
