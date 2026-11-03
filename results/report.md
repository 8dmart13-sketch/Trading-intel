# Copy-trading backtest — 2026-11-03 05:28 UTC

## Bottom line

Copying 20 top traders for the last 30 days, entering **5 min** after them and holding to the end, **made money**: $175.26 on $10,040.00 staked (**1.75%**) across 1004 copied trades.

For comparison, the traders themselves (their own prices, no fees) got 7.55% on the same trades. The gap is what delay + fees cost you.

## All scenarios

| Scenario | Trades | Staked | P&L | ROI | Win rate | Avg price paid vs trader | Worst drawdown |
|---|---|---|---|---|---|---|---|
| Leader's own result (their price, no fees) | 975 | $9,750.00 | $736.50 | 7.55% |  |  | -$158.25 |
| Copy 1 min later, hold to end | 1013 | $10,130.00 | $510.76 | 5.04% |  | +0.36¢ | -$308.46 |
| Copy 1 min later, sell when they sell | 1060 | $10,600.00 | $965.50 | 9.11% | 89.8% | +0.30¢ | -$308.46 |
| Copy 5 min later, hold to end | 1004 | $10,040.00 | $175.26 | 1.75% |  | +0.62¢ | -$318.98 |
| Copy 5 min later, sell when they sell | 1050 | $10,500.00 | $605.82 | 5.77% | 91.7% | +0.69¢ | -$318.98 |
| Copy 15 min later, hold to end | 980 | $9,800.00 | $318.53 | 3.25% |  | +0.58¢ | -$331.79 |
| Copy 15 min later, sell when they sell | 1019 | $10,190.00 | $730.45 | 7.17% | 90.2% | +0.57¢ | -$331.79 |

## By trader (Copy 5 min later, hold to end)

| Trader | Wallet | Copied trades | P&L | ROI |
|---|---|---|---|---|
| monkeymashingkeyboard | `0x684baa57…` | 41 | $173.80 | 42.39% |
| UpTheBlues | `0x2a696600…` | 25 | $173.79 | 69.52% |
| HomeRunHazard | `0x52685279…` | 7 | $52.91 | 75.59% |
| BreakTheBank | `0xf0318c32…` | 41 | $21.35 | 5.21% |
| googleplay | `0xe9b71055…` | 2 | $19.38 | 96.9% |
| Flaznorp | `0x821dab05…` | 148 | $17.84 | 1.21% |
| joseph00677 | `0xcdcccd0f…` | 1 | $0.51 | 5.1% |
| Abkha | `0x7c75be81…` | 12 | -$1.00 | -0.83% |
| balthazar | `0x5a218c7a…` | 126 | -$13.80 | -1.1% |
| Lucerys | `0x1387d145…` | 111 | -$15.20 | -1.37% |
| Bigggggggg | `0x511f9c77…` | 119 | -$17.74 | -1.49% |
| RN1 | `0x2005d16a…` | 61 | -$22.39 | -3.67% |
| Multicoloured-Serf | `0x958bdb8a…` | 74 | -$38.56 | -5.21% |
| e46m3 | `0x4f1d5ae2…` | 114 | -$53.34 | -4.68% |
| takeormake | `0xa38a455b…` | 122 | -$122.29 | -10.02% |

## Read this before trusting the numbers

- **These are best-case results.** Traders were picked *because* they did well recently, then tested on that same period. Real future results will likely be worse.
- Fees are an assumption: 1.0% of each trade, charged on entry and on exit. Change `--fee-rate` to test others.
- Prices are historical market prices, not the exact ask you could have bought at. Real fills, especially in thin markets, would usually be a bit worse.
- 'Still open' trades are valued at today's price, not a final result.
- Each copied trade uses a flat $10.00 stake regardless of how much the trader bet.
- Only covers Polymarket (international). Kalshi and the cheaper-platform comparison come next.

Raw data: `results/backtest.json`. Settings: `{"days": 30, "top": 20, "category": "OVERALL", "period": "MONTH", "wallets": "", "delays": "60,300,900", "stake": 10.0, "fee_rate": 0.01, "max_trades_per_wallet": 1500, "max_signals_per_wallet": 150}`

## Sample of copied trades

| Market | Pick | Trader paid | We paid | P&L | Status |
|---|---|---|---|---|---|
| Spread: Tegevajaro Miyazaki (-1.5) | Tochigi City FC | 0.20 | 0.21 | -$0.10 | open |
| Suns vs. Warriors: O/U 227.5 | Over | 0.95 | 0.96 | -$0.28 | open |
| Will the highest temperature in Manila be 30°C on November 4 | No | 1.00 | 0.98 | -$0.22 | open |
| Will the highest temperature in Manila be 32°C on November 4 | No | 0.68 | 0.66 | $1.35 | open |
| Will the highest temperature in Manila be 35°C on November 4 | No | 0.99 | 0.98 | -$0.10 | open |
| Will the highest temperature in Manila be 31°C on November 4 | No | 0.99 | 0.98 | -$0.29 | open |
| Will the highest temperature in Manila be 34°C on November 4 | No | 0.83 | 0.81 | -$0.10 | open |
| Spread: Ōita Trinita (-1.5) | Vanraure Hachinohe FC | 0.89 | 0.90 | -$0.27 | open |
| Kataller Toyama vs. Vegalta Sendai: 1st Half O/U 0.5 | Under | 0.52 | 0.53 | -$0.01 | open |
| Stoke City FC leading at halftime? | No | 0.71 | 0.72 | -$0.10 | open |
| Suns vs. Warriors: O/U 229.5 | Over | 0.92 | 0.93 | -$0.21 | open |
| Nara Club vs. Thespa Gunma: O/U 2.5 | Under | 0.50 | 0.26 | -$0.29 | open |
| Lincoln City FC leading at halftime? | No | 0.71 | 0.72 | -$0.10 | open |
| KBO Playoff: Samsung Lions vs. KT Wiz | KT Wiz | 0.67 | 0.67 | -$0.10 | open |
| Will the highest temperature in Tel Aviv be 26°C on November | No | 0.97 | 0.95 | -$0.08 | open |
| Will the highest temperature in Tel Aviv be 27°C on November | No | 0.56 | 0.54 | $0.09 | open |
| Will the highest temperature in Tel Aviv be 29°C on November | No | 0.97 | 0.95 | -$0.11 | open |
| Will the highest temperature in Tel Aviv be 28°C on November | No | 0.48 | 0.55 | -$0.10 | open |
| Spread: Brentford FC (-2.5) | Brighton & Hove Albion FC | 0.96 | 0.89 | -$0.10 | open |
| Kataller Toyama vs. Vegalta Sendai: 1st Half O/U 1.5 | Under | 0.85 | 0.87 | -$0.10 | open |
| Spread: Suns (-3.5) | Suns | 0.15 | 0.23 | -$1.19 | open |
| Spread: US Lecce (-2.5) | Torino FC | 0.98 | 0.94 | -$0.10 | open |
| Will Republicans win Alaska, and lose Iowa, Kansas, Maine, M | No | 0.98 | 0.98 | -$0.10 | open |
| Will Republicans win Alaska, Iowa, and Kansas, and lose Main | No | 0.98 | 0.98 | -$0.10 | open |
| Will Republicans win Kansas, and lose Alaska, Iowa, Maine, M | No | 0.97 | 0.97 | -$0.11 | open |
