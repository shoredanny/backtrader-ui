# Backtrader Studio

A local web UI for [backtrader](../backtrader): write strategies in the browser, pick a data feed and run backtests with interactive charts.

## Features

- **Strategies**: browse, create (from a template), edit (Python editor, Ctrl+S to save), rename, duplicate and delete strategy files in `strategies/`. Each save loads the file with backtrader and shows its strategy classes, docstrings and `params`, or the Python error.
- **Backtest**:
  - Pick a strategy file and class. The form lists the strategy's `params` as inputs.
  - Data feed:
    - **Local file**: the CSV files in `../backtrader/datas` plus your uploads
    - **Yahoo Finance**: any ticker via `yfinance` (daily, weekly, monthly or hourly bars)
    - **Upload**: your own CSV with `Date` or `Datetime` plus `Open,High,Low,Close[,Volume]` columns
  - Date range, starting cash, commission, slippage, cheat-on-close, and a sizer (% of cash or a fixed number of units).
  - Results:
    - Summary numbers: return, buy-and-hold, annual return, Sharpe, max drawdown, win rate, SQN
    - Candlestick chart with buy/sell markers and the strategy's indicators (overlaid on price, or in their own panel)
    - Equity curve against buy-and-hold
    - Tables of trades and orders, and anything the strategy `print()`s
- **History**: every successful run is saved in `runs/`. Open an old result, or load its settings back into the form.

## Run

```bash
cd ~/Project/backtrader-ui
npm install      # first time only
npm start        # http://127.0.0.1:3000
```

Environment variables:

| Variable  | Default                      | Purpose |
|-----------|------------------------------|---------|
| `BT_ROOT` | `../backtrader`              | backtrader checkout: gets priority on the Python path, and its `datas/` folder is listed as a data source |
| `PYTHON`  | `$BT_ROOT/env/bin/python`    | Python with backtrader, pandas and yfinance installed |
| `PORT`    | `3000`                       | HTTP port |
| `HOST`    | `127.0.0.1`                  | Bind address. Strategies run arbitrary Python, so keep this on localhost |

## Layout

```
server.js            Express API + static hosting
python/bt_runner.py  Python bridge: `inspect <file>` lists strategy classes, `run` runs a backtest (JSON config on stdin, JSON result on stdout)
public/              Frontend (vanilla JS, CodeMirror 5, TradingView lightweight-charts)
strategies/          Your strategy .py files
data/uploads/        Uploaded CSV feeds
runs/                Saved backtest results (JSON)
```

## Writing strategies

Any `bt.Strategy` subclass in the file is picked up:

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = dict(period=20)          # shown as form inputs in the UI

    def __init__(self):
        self.sma = bt.ind.SMA(period=self.p.period)   # plotted on the price chart

    def next(self):
        if not self.position and self.data.close[0] > self.sma[0]:
            self.buy()                 # size comes from the sizer in the form
        elif self.position and self.data.close[0] < self.sma[0]:
            self.close()
```

The UI converts each parameter to the type of its default value (int, float, bool or str).
