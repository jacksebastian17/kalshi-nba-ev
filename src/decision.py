from __future__ import annotations
from dataclasses import dataclass

from src.math_utils import kalshi_edge_yes, kalshi_edge_no


@dataclass(frozen=True)
class Decision:
    action: str  # "BUY_YES", "BUY_NO", "SKIP"
    edge: float  # best edge per share (ignoring fees)
    reason: str


def decide(
    p_true_yes: float,
    ask_yes: float | None,
    ask_no: float | None,
    edge_threshold: float = 0.02,
    slippage_buffer: float = 0.005,
) -> Decision:
    """
    V1 decision rule:
      - Compute edges for BUY YES and BUY NO (ignore fees for now).
      - Subtract slippage_buffer from the edge (roughly accounts for spread/fees noise).
      - If best adjusted edge >= edge_threshold -> take that side.
      - Else SKIP.
    """
    candidates: list[tuple[str, float]] = []

    if ask_yes is not None:
        edge_yes = kalshi_edge_yes(p_true_yes, ask_yes) - slippage_buffer
        candidates.append(("BUY_YES", edge_yes))

    if ask_no is not None:
        edge_no = kalshi_edge_no(p_true_yes, ask_no) - slippage_buffer
        candidates.append(("BUY_NO", edge_no))

    if not candidates:
        return Decision(action="SKIP", edge=0.0, reason="No prices available")

    best_action, best_edge = max(candidates, key=lambda x: x[1])

    if best_edge >= edge_threshold:
        return Decision(action=best_action, edge=best_edge, reason="Edge above threshold")
    return Decision(action="SKIP", edge=best_edge, reason="Edge below threshold")