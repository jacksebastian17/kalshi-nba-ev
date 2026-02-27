from src.scanner import evaluate_market
from src.kalshi_public import KalshiTop


def test_evaluate_market_delegates(monkeypatch):
    # stub out the Kalshi call so we control prices
    fake_top = KalshiTop(bid_yes=0.6, bid_no=0.4, ask_yes=0.4, ask_no=0.6)

    monkeypatch.setattr(
        "src.scanner.get_orderbook_top",
        lambda ticker, key_id=None, key_file_path=None, use_pkcs1=False: fake_top,
    )
    monkeypatch.setattr(
        "src.kalshi_public.get_orderbook_top",
        lambda ticker, key_id=None, key_file_path=None, use_pkcs1=False: fake_top,
    )

    # with p_true_yes 0.55 the yes side has good edge
    decision = evaluate_market(
        "SOME", p_true_yes=0.55, edge_threshold=0.01, slippage_buffer=0.0
    )
    assert decision.action == "BUY_YES"
    assert decision.edge > 0
