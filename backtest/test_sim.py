"""Offline checks of the P&L math. Run: python backtest/test_sim.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sim import build_signals, simulate  # noqa: E402

trades = [
    # trader buys YES on market A in two fills 2 min apart -> one signal
    {"wallet": "w1", "side": "BUY", "asset": "A", "conditionId": "cA", "outcomeIndex": 0,
     "price": 0.40, "size": 100, "timestamp": 1000, "title": "Market A", "outcome": "Yes"},
    {"wallet": "w1", "side": "BUY", "asset": "A", "conditionId": "cA", "outcomeIndex": 0,
     "price": 0.50, "size": 100, "timestamp": 1120, "title": "Market A", "outcome": "Yes"},
    # buys market B, later sells
    {"wallet": "w1", "side": "BUY", "asset": "B", "conditionId": "cB", "outcomeIndex": 1,
     "price": 0.60, "size": 50, "timestamp": 2000, "title": "Market B", "outcome": "No"},
    {"wallet": "w1", "side": "SELL", "asset": "B", "conditionId": "cB", "outcomeIndex": 1,
     "price": 0.80, "size": 50, "timestamp": 5000, "title": "Market B", "outcome": "No"},
]
sigs, exits = build_signals(trades)
assert len(sigs) == 2 and len(exits) == 1
assert abs(sigs[0].trader_price - 0.45) < 1e-9, sigs[0].trader_price

price = {("A", 1300): 0.50, ("B", 2300): 0.65, ("B", 5300): 0.75, ("B", 5000): 0.80}
price_at = lambda tok, ts: price.get((tok, ts))
settle = lambda cid, idx: {"cA": (1.0, "resolved"), "cB": (0.0, "resolved")}[cid]

r = simulate(sigs, exits, delay=300, stake=10, fee_rate=0.01, price_at=price_at,
             settle=settle, follow_exits=False, label="hold")
s = r.summary()
# A: 10/0.5=20 shares *1 -10 -0.1 = 9.9 ; B: 10/0.65 *0 -10 -0.1 = -10.1
assert abs(s["pnl"] - (-0.2)) < 1e-6, s
assert s["win_rate_pct"] == 50.0

r = simulate(sigs, exits, delay=300, stake=10, fee_rate=0.01, price_at=price_at,
             settle=settle, follow_exits=True, label="follow")
s = r.summary()
b_exit = (10 / 0.65) * 0.75
b_pnl = b_exit - b_exit * 0.01 - 10 - 0.1
assert abs(s["pnl"] - round(9.9 + b_pnl, 2)) < 0.01, (s, 9.9 + b_pnl)

r = simulate(sigs, exits, delay=0, stake=10, fee_rate=0.01, price_at=price_at,
             settle=settle, follow_exits=False, label="leader", use_trader_price=True)
s = r.summary()
assert abs(s["pnl"] - (10 / 0.45 - 10 - 10)) < 0.01, s
print("all checks passed")
