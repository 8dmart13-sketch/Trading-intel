"""Pure simulation logic for the copy-trade backtest (no network calls).

A "signal" is one decision by a followed trader to buy into an outcome.
We copy each signal with a fixed dollar stake, entering `delay` seconds
after the trader did, at whatever the market price was by then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MERGE_WINDOW = 600  # buys of the same outcome within 10 min = one signal


@dataclass
class Signal:
    wallet: str
    asset: str          # outcome token id
    condition_id: str   # market id
    outcome_index: int
    title: str
    outcome: str
    ts: int             # time of the trader's first fill
    trader_price: float # trader's average fill price
    trader_usd: float


@dataclass
class Exit:
    wallet: str
    asset: str
    ts: int


def build_signals(trades: list[dict]) -> tuple[list[Signal], list[Exit]]:
    """Collapse raw fills into buy signals and sell (exit) events."""
    signals: list[Signal] = []
    exits: list[Exit] = []
    open_sig: dict[tuple[str, str], Signal] = {}
    for t in sorted(trades, key=lambda x: int(x["timestamp"])):
        key = (t["wallet"], t["asset"])
        ts = int(t["timestamp"])
        price = float(t["price"])
        size = float(t["size"])
        if t["side"].upper() == "BUY":
            s = open_sig.get(key)
            if s and ts - s.ts <= MERGE_WINDOW:
                total = s.trader_usd + price * size
                shares = s.trader_usd / s.trader_price + size
                s.trader_usd = total
                s.trader_price = total / shares if shares else s.trader_price
            else:
                s = Signal(t["wallet"], t["asset"], t.get("conditionId", ""),
                           int(t.get("outcomeIndex", 0) or 0), t.get("title", ""),
                           t.get("outcome", ""), ts, price, price * size)
                open_sig[key] = s
                signals.append(s)
        else:
            exits.append(Exit(t["wallet"], t["asset"], ts))
    return signals, exits


@dataclass
class Result:
    label: str
    trades: list[dict] = field(default_factory=list)
    skipped_no_price: int = 0
    skipped_extreme: int = 0

    def summary(self) -> dict:
        n = len(self.trades)
        staked = sum(t["stake"] for t in self.trades)
        pnl = sum(t["pnl"] for t in self.trades)
        resolved = [t for t in self.trades if t["status"] == "resolved"]
        wins = sum(1 for t in resolved if t["pnl"] > 0)
        slips = [t["slippage_c"] for t in self.trades if t["slippage_c"] is not None]
        # worst peak-to-trough on cumulative P&L, in time order
        cum = peak = dd = 0.0
        for t in sorted(self.trades, key=lambda x: x["ts"]):
            cum += t["pnl"]
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        return {
            "label": self.label,
            "copied_trades": n,
            "total_staked": round(staked, 2),
            "pnl": round(pnl, 2),
            "roi_pct": round(100 * pnl / staked, 2) if staked else 0.0,
            "resolved": len(resolved),
            "still_open": n - len(resolved),
            "win_rate_pct": round(100 * wins / len(resolved), 1) if resolved else None,
            "avg_slippage_cents": round(sum(slips) / len(slips), 2) if slips else None,
            "max_drawdown": round(dd, 2),
            "skipped_no_price": self.skipped_no_price,
            "skipped_extreme_price": self.skipped_extreme,
        }


PriceFn = Callable[[str, int], Optional[float]]
SettleFn = Callable[[str, int], tuple[Optional[float], str]]  # (payout per share, status)


def simulate(signals: list[Signal], exits: list[Exit], *, delay: int,
             stake: float, fee_rate: float, price_at: PriceFn,
             settle: SettleFn, follow_exits: bool, label: str,
             use_trader_price: bool = False) -> Result:
    """Copy every signal with `stake` dollars.

    use_trader_price=True gives the "leader's own result" baseline:
    the trader's fill price, no delay, no fees.
    follow_exits=True sells our copy the first time the trader sells that
    outcome after our entry; otherwise we hold until the market settles.
    """
    res = Result(label)
    exits_by_key: dict[tuple[str, str], list[int]] = {}
    for e in exits:
        exits_by_key.setdefault((e.wallet, e.asset), []).append(e.ts)
    for v in exits_by_key.values():
        v.sort()

    for s in signals:
        if use_trader_price:
            entry, fee = s.trader_price, 0.0
        else:
            entry = price_at(s.asset, s.ts + delay)
            fee = stake * fee_rate
        if entry is None:
            res.skipped_no_price += 1
            continue
        if entry <= 0.01 or entry >= 0.99:
            res.skipped_extreme += 1
            continue
        shares = stake / entry
        exit_value: Optional[float] = None
        status = ""
        if follow_exits:
            later = [ts for ts in exits_by_key.get((s.wallet, s.asset), []) if ts > s.ts]
            if later:
                xp = price_at(s.asset, later[0] + (0 if use_trader_price else delay))
                if xp is not None:
                    exit_value = shares * xp
                    if not use_trader_price:
                        exit_value -= exit_value * fee_rate
                    status = "resolved"  # closed out = realized
        if exit_value is None:
            payout, status = settle(s.condition_id, s.outcome_index)
            if payout is None:
                res.skipped_no_price += 1
                continue
            exit_value = shares * payout
        pnl = exit_value - stake - fee
        res.trades.append({
            "wallet": s.wallet, "title": s.title, "outcome": s.outcome,
            "ts": s.ts, "trader_price": round(s.trader_price, 4),
            "our_price": round(entry, 4),
            "slippage_c": None if use_trader_price else round(100 * (entry - s.trader_price), 2),
            "stake": stake, "pnl": round(pnl, 4), "status": status,
        })
    return res
