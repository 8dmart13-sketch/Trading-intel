"""Polymarket copy-trading backtest.

Pulls the top traders from Polymarket's public leaderboard (or wallets you
give it), replays every buy they made in the last N days, and works out
what you would have made copying them after a delay, after fees.

Read-only. No account, keys or money involved.

Usage:
  python backtest/run.py --days 30 --top 20 --category OVERALL
  python backtest/run.py --wallets 0xabc...,0xdef...
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).parent))
from sim import build_signals, simulate  # noqa: E402

DATA = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = {"User-Agent": "trading-intel-backtest/1.0", "Accept": "application/json"}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results"


# ---------------------------------------------------------------- HTTP

_err_count = {"n": 0}


def note_error(msg: str):
    """Print the first few errors in full, then just count the rest."""
    _err_count["n"] += 1
    if _err_count["n"] <= 8:
        print(f"  {msg}", file=sys.stderr)


def rows_of(resp):
    """Data API v2 wraps lists as {"data": [...], "pagination": {...}}."""
    if isinstance(resp, list):
        return resp, None
    if isinstance(resp, dict):
        nxt = (resp.get("pagination") or {}).get("next_cursor")
        return resp.get("data") or [], nxt
    return [], None

def get(base: str, path: str, params: dict | None = None, tries: int = 5):
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            body = e.read().decode(errors="replace")[:300]
            note_error(f"HTTP {e.code} {url} :: {body}")
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            note_error(f"network error {url} :: {e}")
            return None


# ---------------------------------------------------------------- data

def leaderboard(category: str, period: str, top: int) -> list[dict]:
    resp = get(DATA, "/v2/leaderboard", {
        "category": category.lower(), "time_period": period.lower(),
        "sort_by": "PNL", "limit": top,
    })
    rows, _ = rows_of(resp)
    if rows:
        print(f"  sample leaderboard row: {json.dumps(rows[0])[:300]}")
    out = []
    for r in rows[:top]:
        w = (r.get("user_id") or r.get("proxy_wallet") or r.get("wallet")
             or r.get("proxyWallet") or r.get("address"))
        if w:
            out.append({"wallet": str(w).lower(),
                        "name": r.get("user_name") or r.get("userName") or r.get("name") or "",
                        "lb_pnl": r.get("pnl"), "lb_volume": r.get("volume") or r.get("vol")})
    return out


def normalize_trade(t: dict, wallet: str) -> dict:
    """Map v2 snake_case fields onto the names sim.py expects."""
    return {
        "wallet": wallet,
        "side": t.get("side", ""),
        "asset": str(t.get("token_id") or t.get("asset") or ""),
        "conditionId": t.get("condition_id") or t.get("conditionId") or "",
        "outcomeIndex": t.get("outcome_index", t.get("outcomeIndex")),
        "price": t.get("price", 0),
        "size": t.get("size", 0),
        "timestamp": t.get("timestamp", 0),
        "title": t.get("title") or "",
        "outcome": t.get("outcome") or "",
    }


_printed_trade_sample = {"done": False}


def trades_for(wallet: str, since: int, cap: int) -> list[dict]:
    out, cursor = [], None
    base = {"user": wallet, "limit": 1000, "taker_only": "false", "start": since}
    while len(out) < cap:
        params = dict(base, cursor=cursor) if cursor else base
        rows, cursor = rows_of(get(DATA, "/v2/trades", params))
        if rows and not _printed_trade_sample["done"]:
            print(f"  sample trade row: {json.dumps(rows[0])[:300]}")
            _printed_trade_sample["done"] = True
        for t in rows:
            if int(t.get("timestamp", 0) or 0) >= since:
                out.append(normalize_trade(t, wallet))
        if not cursor or not rows:
            break
    return out[:cap]


class Prices:
    """Market price of an outcome token at (or just after) a moment in time."""

    def __init__(self):
        self.cache: dict[tuple[str, int], float | None] = {}
        self.lock = Lock()

    def __call__(self, token: str, ts: int):
        key = (token, ts // 60)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        data = get(CLOB, "/prices-history", {"market": token, "startTs": ts - 60,
                                             "endTs": ts + 1800, "fidelity": 1})
        hist = (data or {}).get("history") or []
        p = None
        for pt in sorted(hist, key=lambda x: x["t"]):
            if pt["t"] >= ts:
                p = float(pt["p"])
                break
        if p is None and hist:
            p = float(sorted(hist, key=lambda x: x["t"])[-1]["p"])
        with self.lock:
            self.cache[key] = p
        return p


class Settlements:
    """Payout per share for an outcome: 1/0 once settled, else current price."""

    def __init__(self):
        self.cache: dict[str, dict | None] = {}
        self.token_index: dict[str, int] = {}

    def load(self, condition_ids: set[str]):
        ids = [c for c in condition_ids if c and c not in self.cache]
        for i in range(0, len(ids), 20):
            chunk = ids[i:i + 20]
            rows = get(GAMMA, "/markets", [("condition_ids", c) for c in chunk]
                       + [("limit", 50)]) if chunk else []
            for m in (rows if isinstance(rows, list) else rows_of(rows)[0]) or []:
                self.cache[(m.get("conditionId") or "").lower()] = m
                toks = m.get("clobTokenIds")
                try:
                    toks = json.loads(toks) if isinstance(toks, str) else (toks or [])
                except json.JSONDecodeError:
                    toks = []
                for i, tok in enumerate(toks):
                    self.token_index[str(tok)] = i
            for c in chunk:
                self.cache.setdefault(c.lower(), None)

    def __call__(self, condition_id: str, outcome_index: int):
        m = self.cache.get((condition_id or "").lower())
        if not m:
            return None, "unknown"
        try:
            prices = m.get("outcomePrices")
            prices = json.loads(prices) if isinstance(prices, str) else prices
            p = float(prices[outcome_index])
        except (TypeError, ValueError, IndexError, json.JSONDecodeError):
            return None, "unknown"
        if m.get("closed") and (p >= 0.99 or p <= 0.01):
            return (1.0 if p >= 0.99 else 0.0), "resolved"
        return p, "open"


# ---------------------------------------------------------------- report

def fmt_money(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def write_report(meta, summaries, per_wallet, sample):
    lines = [f"# Copy-trading backtest — {meta['run_at']}", ""]
    base = next((s for s in summaries if s["label"].startswith("Leader")), None)
    key = next((s for s in summaries if s["label"] == meta["headline"]), None)
    if key:
        verdict = "made money" if key["pnl"] > 0 else "lost money"
        lines += ["## Bottom line", "",
                  f"Copying {meta['n_wallets']} top traders for the last {meta['days']} days, "
                  f"entering **{meta['headline_delay_min']} min** after them and holding to the end, "
                  f"**{verdict}**: {fmt_money(key['pnl'])} on {fmt_money(key['total_staked'])} staked "
                  f"(**{key['roi_pct']}%**) across {key['copied_trades']} copied trades.", ""]
        if base:
            lines += [f"For comparison, the traders themselves (their own prices, no fees) got "
                      f"{base['roi_pct']}% on the same trades. The gap is what delay + fees cost you.", ""]
    lines += ["## All scenarios", "",
              "| Scenario | Trades | Staked | P&L | ROI | Win rate | Avg price paid vs trader | Worst drawdown |",
              "|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        slip = "" if s["avg_slippage_cents"] is None else f"{s['avg_slippage_cents']:+.2f}¢"
        wr = "" if s["win_rate_pct"] is None else f"{s['win_rate_pct']}%"
        lines.append(f"| {s['label']} | {s['copied_trades']} | {fmt_money(s['total_staked'])} | "
                     f"{fmt_money(s['pnl'])} | {s['roi_pct']}% | {wr} | {slip} | {fmt_money(s['max_drawdown'])} |")
    lines += ["", f"## By trader ({meta['headline']})", "",
              "| Trader | Wallet | Copied trades | P&L | ROI |", "|---|---|---|---|---|"]
    for w in per_wallet:
        lines.append(f"| {w['name'] or '—'} | `{w['wallet'][:10]}…` | {w['n']} | "
                     f"{fmt_money(w['pnl'])} | {w['roi_pct']}% |")
    lines += ["", "## Read this before trusting the numbers", "",
              "- **These are best-case results.** Traders were picked *because* they did well recently, "
              "then tested on that same period. Real future results will likely be worse.",
              f"- Fees are an assumption: {meta['fee_rate']*100:.1f}% of each trade, charged on entry and on exit. "
              "Change `--fee-rate` to test others.",
              "- Prices are historical market prices, not the exact ask you could have bought at. "
              "Real fills, especially in thin markets, would usually be a bit worse.",
              "- 'Still open' trades are valued at today's price, not a final result.",
              f"- Each copied trade uses a flat {fmt_money(meta['stake'])} stake regardless of how much the trader bet.",
              "- Only covers Polymarket (international). Kalshi and the cheaper-platform comparison come next.",
              "", f"Raw data: `results/backtest.json`. Settings: `{json.dumps(meta['args'])}`"]
    if sample:
        lines += ["", "## Sample of copied trades", "",
                  "| Market | Pick | Trader paid | We paid | P&L | Status |", "|---|---|---|---|---|---|"]
        for t in sample:
            lines.append(f"| {t['title'][:60]} | {t['outcome']} | {t['trader_price']:.2f} | "
                         f"{t['our_price']:.2f} | {fmt_money(t['pnl'])} | {t['status']} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--category", default="OVERALL", help="OVERALL, SPORTS, POLITICS, CRYPTO, ...")
    ap.add_argument("--period", default="MONTH", help="leaderboard window: DAY, WEEK, MONTH, ALL")
    ap.add_argument("--wallets", default="", help="comma-separated wallets; overrides leaderboard")
    ap.add_argument("--delays", default="60,300,900", help="seconds after trader to copy")
    ap.add_argument("--stake", type=float, default=10.0)
    ap.add_argument("--fee-rate", type=float, default=0.01)
    ap.add_argument("--max-trades-per-wallet", type=int, default=1500)
    ap.add_argument("--max-signals-per-wallet", type=int, default=150)
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    since = int(time.time()) - a.days * 86400
    delays = [int(d) for d in a.delays.split(",") if d.strip()]
    headline_delay = 300 if 300 in delays else delays[0]

    if a.wallets.strip():
        traders = [{"wallet": w.strip().lower(), "name": "", "lb_pnl": None, "lb_volume": None}
                   for w in a.wallets.split(",") if w.strip()]
    else:
        print(f"Leaderboard: {a.category} / {a.period} / top {a.top}")
        traders = leaderboard(a.category, a.period, a.top)
    if not traders:
        sys.exit("No traders found (leaderboard empty or blocked). Check the log above.")
    names = {t["wallet"]: t["name"] for t in traders}

    settle = Settlements()
    all_signals, all_exits = [], []
    for t in traders:
        raw = trades_for(t["wallet"], since, a.max_trades_per_wallet)
        settle.load({r["conditionId"] for r in raw})
        for r in raw:
            if r["outcomeIndex"] is None:
                r["outcomeIndex"] = settle.token_index.get(r["asset"], 0)
        sigs, exits = build_signals(raw)
        sigs = sorted(sigs, key=lambda s: s.ts)[-a.max_signals_per_wallet:]
        print(f"  {t['name'] or t['wallet'][:10]}: {len(raw)} fills -> {len(sigs)} buy signals")
        all_signals += sigs
        all_exits += exits
    if not all_signals:
        sys.exit("No buy trades found in the window.")

    prices = Prices()

    # warm the price cache in parallel (the slow part)
    needed = {(s.asset, s.ts + d) for s in all_signals for d in delays}
    by_key = {}
    for e in all_exits:
        by_key.setdefault((e.wallet, e.asset), []).append(e.ts)
    for s in all_signals:
        later = sorted(ts for ts in by_key.get((s.wallet, s.asset), []) if ts > s.ts)
        if later:
            needed |= {(s.asset, later[0] + d) for d in delays + [0]}
    print(f"Fetching {len(needed)} historical prices…")
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda k: prices(*k), needed))
    got = sum(1 for v in prices.cache.values() if v is not None)
    print(f"  got {got} of {len(prices.cache)} prices; {_err_count['n']} request errors total")

    common = dict(stake=a.stake, fee_rate=a.fee_rate, price_at=prices, settle=settle)
    runs = [simulate(all_signals, all_exits, delay=0, follow_exits=False,
                     label="Leader's own result (their price, no fees)",
                     use_trader_price=True, **common)]
    for d in delays:
        m = d // 60 if d >= 60 else d
        unit = "min" if d >= 60 else "sec"
        runs.append(simulate(all_signals, all_exits, delay=d, follow_exits=False,
                             label=f"Copy {m} {unit} later, hold to end", **common))
        runs.append(simulate(all_signals, all_exits, delay=d, follow_exits=True,
                             label=f"Copy {m} {unit} later, sell when they sell", **common))
    summaries = [r.summary() for r in runs]
    headline_label = f"Copy {headline_delay // 60} min later, hold to end"
    head = next(r for r in runs if r.label == headline_label)

    per = {}
    for t in head.trades:
        p = per.setdefault(t["wallet"], {"wallet": t["wallet"], "name": names.get(t["wallet"], ""),
                                         "n": 0, "pnl": 0.0, "staked": 0.0})
        p["n"] += 1
        p["pnl"] += t["pnl"]
        p["staked"] += t["stake"]
    per_wallet = sorted(per.values(), key=lambda x: -x["pnl"])
    for p in per_wallet:
        p["pnl"] = round(p["pnl"], 2)
        p["roi_pct"] = round(100 * p["pnl"] / p["staked"], 2) if p["staked"] else 0

    meta = {"run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "days": a.days, "n_wallets": len(traders), "stake": a.stake,
            "fee_rate": a.fee_rate, "headline": headline_label,
            "headline_delay_min": headline_delay // 60, "args": vars(a)}
    sample = sorted(head.trades, key=lambda t: -t["ts"])[:25]
    (OUT / "backtest.json").write_text(json.dumps(
        {"meta": meta, "traders": traders, "summaries": summaries,
         "per_wallet": per_wallet, "trades": head.trades}, indent=1))
    write_report(meta, summaries, per_wallet, sample)
    print((OUT / "report.md").read_text())


if __name__ == "__main__":
    main()
