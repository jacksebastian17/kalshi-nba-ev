from src.scanner import evaluate_market
from src.kalshi_public import KalshiTop


def test_evaluate_market_delegates(monkeypatch):
    # stub out the Kalshi call so we control prices
    # Use prices above 5c to pass the new price filter
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
    # fee on 75c = ceil(0.07 * 0.75 * 0.25) = ceil(0.013125) = $0.02 (2%)
    # net edge = 10% - 2% - 0% = 8% (above threshold)
    decision = evaluate_market(
        "SOME", p_true_yes=0.85, edge_threshold=0.01, slippage_buffer=0.0, fee_maker=False, min_price=0.05
    )
    assert decision.action == "BUY_YES"
    assert decision.edge > 0
