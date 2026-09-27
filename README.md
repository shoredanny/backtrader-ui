# Backtrader Studio

A local web UI for [backtrader](../backtrader): write strategies in the browser, pick a data feed and run backtests with interactive charts.

## Features

- **Strategies**: a folder tree of the strategy files in `strategies/`. Browse, filter, create (from a template, optionally inside a `folder/`), edit (Python editor, Ctrl+S to save), rename/move, duplicate and delete them. Each save loads the file with backtrader and shows its description, strategy classes, `params`, sample options and backtest defaults, or the Python error.
- **Ported backtrader samples**: every script in `backtrader/samples` is available as a strategy file under the same `folder/file.py` path (see [Ported samples](#ported-samples)).
- **Backtest**:
  - Pick a strategy file and class. The form lists the strategy's `params` as inputs, plus the file's sample options, and applies the file's default feed, dates, cash, commission and sizer.
  - Data feed:
    - **Local file**: the CSV files in `../backtrader/datas` plus your uploads
    - **Yahoo Finance**: any ticker via `yfinance` (daily, weekly, monthly or hourly bars)
    - **Upload**: your own CSV with `Date` or `Datetime` plus `Open,High,Low,Close[,Volume]` columns
  - Date range, starting cash, commission, slippage, cheat-on-close, and a sizer (% of cash or a fixed number of units).
  - Results:
    - Summary numbers: return, buy-and-hold, annual return, Sharpe, max drawdown, win rate, SQN
    - Candlestick chart with buy/sell markers and the strategy's indicators (overlaid on price, or in their own panel), plus panels for observers and additional data feeds
    - Equity curve against buy-and-hold
    - Tables of trades and orders, the output of any analyzers the file adds, and anything the strategy `print()`s (including WriterFile output)
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
strategies/          Strategy .py files (sub-folders allowed; ported samples live in their sample folder)
data/uploads/        Uploaded CSV feeds
runs/                Saved backtest results (JSON)
tools/               port_samples.py (regenerates the sample ports), test_strategies.py (runs every strategy with its defaults)
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

The UI converts each parameter to the type of its default value (int, float, bool or str). Other defaults (classes such as `bt.ind.SMA`, lists, `datetime` values) are edited as Python expressions.

Files can import helper modules stored next to them (e.g. `from relativevolume import RelativeVolume`).

### Optional module-level setup

A strategy file can also control how it is run. All of these are optional:

```python
# Values the backtest form pre-selects when this file is chosen
DEFAULTS = dict(
    feed='orcl-1995-2014.txt',        # a file from backtrader/datas or uploads, or 'yahoo:TICKER[:interval]'
    fromdate='2005-01-01', todate='2006-12-31',
    cash=100000.0, commission=0.0,    # commission in percent
    slippage=0.0, coc=False,
    sizer=dict(type='fixed', value=1),  # or dict(type='percent', value=95)
    strategy='MyStrategy',            # class to select when the file has several
    params=dict(period=30),           # param values to use instead of the class defaults
)

# Extra run settings shown as "Sample options"; configure() reads them from ctx.opts
OPTIONS = dict(timeframe='weekly', replay=False)

# Allowed values for params/options, shown as dropdowns
CHOICES = dict(timeframe=['daily', 'weekly', 'monthly'])


def configure(cerebro, data, ctx):
    '''Called before the run, after the form's broker and sizer settings are
    applied (so it may override them). `data` is the selected feed; if
    configure adds no feed, the runner adds `data` itself.'''
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks)
    cerebro.addanalyzer(bt.analyzers.SQN)
```

Inside `configure()`, `ctx` provides:

- `ctx.opts`: the option values chosen in the form
- `ctx.fromdate` / `ctx.todate`: the form's dates
- `ctx.load('file.txt' | 'yahoo:GLD')`: load another feed for the same dates
- `ctx.make_data(timeframe=..., sessionend=...)`: a fresh copy of the selected feed with some feed parameters changed
- `ctx.datapath(name)`: the full path of a file in `backtrader/datas`

`configure()` may also add companion strategies with `cerebro.addstrategy`. The class selected in the form always runs first, and the results are read from it.

## Ported samples

Every script in `backtrader/samples` was ported, 84 files in all, keeping the same folder and file names. In each port:

- The strategy, indicator, observer, sizer and filter code is unchanged.
- The command-line code (`argparse`, `runstrat()`, `__main__`) is replaced by a Backtrader Studio setup section at the end of the file (`DEFAULTS`, `OPTIONS`, `CHOICES`, `configure()`) that does what `runstrat()` did.
- The sample's command-line flags became options or params, with the same defaults.
- The module docstring explains what the sample demonstrates, plus any differences from the original.
- Helper modules imported by other samples (`relativevolume.py`, `mtradeobserver.py`, `orderobserver.py`, `pivotpoint.py`, `relvolbybar.py`, `weekdaysfiller.py`) are copied unchanged. They appear dimmed in the tree and can't be run on their own.

Where the output is deterministic, the ports print exactly the same log as the original scripts.

Known differences:

| Sample | Note |
|---|---|
| `talib/*` | Needs the TA-Lib Python package (not installed in the backtrader env). Without it the run stops with a clear message. |
| `ibtest`, `oandatest`, `vctest`, `ib-cash-bid-ask` | Live-trading samples. They run on historical data here; a `backtest` param makes them trade as if the data were live. |
| `gold-vs-sp500` | scipy isn't installed, so the correlation falls back to `numpy.corrcoef` (same result). |
| `pyfolio2`, `pyfoliotest` | The PyFolio analyzer output is shown in the Analyzers tab. pyfolio itself (the tear sheet) isn't installed. `pyfolio2` used VisualChart data; it now uses the selected feed. It also had an infinite-recursion bug with this backtrader version, which is fixed. |
| `rollover` | Chains or rolls over local files (option `files`) instead of the VisualChart FESX futures contracts. |
| `sigsmacross`, `tradingcalendar/tcal`, `yahoo-test` | YHOO is no longer on Yahoo. They use the offline yhoo file, SPY or AAPL instead. |
| `tradingcalendar/tcal-intra` | Its 2016 intraday file isn't in `backtrader/datas`; `2006-min-005.txt` is the default instead. |
| `lrsi` | `LaguerreRSI2`/`LaguerreRSI3` don't exist in this backtrader version; `LaguerreFilter` is shown instead. |
| `calendar-days`, `order-close/close-daily`, `observer-benchmark` | Fixed small Python 3 bugs from the originals. |
| `optimization`, `strategy-selection`, `multi-copy` | The UI runs one parameter set or class at a time; there's no optimization run. `multi-copy` adds the second strategy through `configure()`. |
| `signals-strategy`, `slippage`, `credit-interest` | Signals added with `cerebro.add_signal` are now created in the strategy class from params. |

The porting script (`tools/port_samples.py`) regenerates all ports and **overwrites** these files. Re-run it only on files you haven't edited.
