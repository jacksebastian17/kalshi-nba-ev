from src.scanner import evaluate_market
from src.kalshi_public import KalshiTop


def test_evaluate_market_delegates(monkeypatch):
    # stub out the Kalshi call so we control prices
    # Use prices above 70c to pass the new price filter
    fake_top = KalshiTop(bid_yes=0.75, bid_no=0.25, ask_yes=0.75, ask_no=0.25)

    monkeypatch.setattr(
        "src.scanner.get_orderbook_top",
        lambda ticker, key_id=None, key_file_path=None, use_pkcs1=False: fake_top,
    )
    monkeypatch.setattr(
        "src.kalshi_public.get_orderbook_top",
        lambda ticker, key_id=None, key_file_path=None, use_pkcs1=False: fake_top,
    )

    # with p_true_yes 0.85 and ask_yes=0.75, we have 10% raw edge
    # After fees (~2.5% on 75c contract), still positive
    decision = evaluate_market(
        "SOME", p_true_yes=0.85, edge_threshold=0.01, slippage_buffer=0.0, fee_rate=0.10, min_price=0.70
    )
    assert decision.action == "BUY_YES"
    assert decision.edge > 0
