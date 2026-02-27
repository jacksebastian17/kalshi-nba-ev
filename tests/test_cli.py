import argparse
import pytest

from src import cli
from src.kalshi_public import KalshiTop
from src.decision import Decision


def test_parse_args_defaults():
    ns = cli.parse_args(["--ticker", "FOO"])
    assert ns.ticker == "FOO"
    assert ns.action == "top"


def test_compute_p_true_decimal():
    args = argparse.Namespace(dec_yes=1.9, dec_no=2.1, amer_yes=None, amer_no=None)
    p = cli.compute_p_true(args)
    # p should equal the fair (de-vigged) probability from sharp_model
    expected = cli.fair_prob_from_two_way(cli.TwoWayOdds(dec_yes=1.9, dec_no=2.1))
    assert pytest.approx(p) == expected


def test_compute_p_true_american():
    args = argparse.Namespace(dec_yes=None, dec_no=None, amer_yes=150, amer_no=-120)
    p = cli.compute_p_true(args)
    assert 0.0 < p < 1.0


def test_main_top(monkeypatch, capsys):
    # stub book fetch; patch both cli and kalshi_public references
    fake = KalshiTop(bid_yes=0.5, bid_no=0.5, ask_yes=0.5, ask_no=0.5)
    monkeypatch.setattr(cli, "get_orderbook_top", lambda t, key_id=None, key_file_path=None, use_pkcs1=False: fake)
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", lambda t, key_id=None, key_file_path=None, use_pkcs1=False: fake)
    ret = cli.main(["--ticker", "T", "--action", "top"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "KalshiTop" in captured.out


def test_main_top_with_api_key(monkeypatch, capsys):
    # ensure the CLI passes key_id through to get_orderbook_top
    captured = {}
    def fake_get(ticker, key_id=None, key_file_path=None, use_pkcs1=False):
        captured['key_id'] = key_id
        captured['key_file_path'] = key_file_path
        return KalshiTop(bid_yes=0, bid_no=0, ask_yes=0, ask_no=0)
    monkeypatch.setattr(cli, "get_orderbook_top", fake_get)
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", fake_get)
    ret = cli.main(["--ticker", "T", "--action", "top", "--key-id", "KEY123", "--key-file", "test.pem"])
    assert ret == 0
    assert captured['key_id'] == "KEY123"
    assert captured['key_file_path'] == "test.pem"


def test_main_eval_success(monkeypatch, capsys):
    fake = KalshiTop(bid_yes=0.6, bid_no=0.4, ask_yes=0.4, ask_no=0.6)
    monkeypatch.setattr(cli, "get_orderbook_top", lambda t, key_id=None, key_file_path=None, use_pkcs1=False: fake)
    monkeypatch.setattr("src.kalshi_public.get_orderbook_top", lambda t, key_id=None, key_file_path=None, use_pkcs1=False: fake)
    ret = cli.main([
        "--ticker",
        "T",
        "--action",
        "eval",
        "--dec-yes",
        "1.9",
        "--dec-no",
        "1.9",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Decision" in captured.out


def test_main_eval_missing_odds(capsys):
    ret = cli.main(["--ticker", "T", "--action", "eval"])
    assert ret == 1
    out = capsys.readouterr()
    assert "must supply" in out.err
