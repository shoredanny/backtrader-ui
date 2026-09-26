#!/usr/bin/env python
'''Bridge between the Node.js UI and backtrader.

Usage:
  bt_runner.py inspect <strategy_file.py>   -> JSON list of strategy classes
  bt_runner.py run                          -> reads JSON config on stdin,
                                               writes JSON results on stdout
'''
import calendar
import contextlib
import importlib.util
import inspect
import io
import json
import math
import os
import sys
import traceback
import uuid
from datetime import datetime

# Prefer the backtrader source checkout (with local modifications) over the
# copy installed in site-packages
BT_ROOT = os.environ.get('BT_ROOT')
if BT_ROOT:
    sys.path.insert(0, BT_ROOT)

import backtrader as bt  # noqa: E402


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def emit(obj):
    sys.__stdout__.write(json.dumps(obj, default=str, allow_nan=False))
    sys.__stdout__.flush()


def clean(v):
    '''Make a value JSON safe (NaN/inf -> None)'''
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def ts(dt):
    '''naive datetime -> unix seconds, treating the wall time as UTC so the
    chart shows the same clock time as the data'''
    return calendar.timegm(dt.timetuple())


def load_module(path):
    name = 'userstrat_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def strategy_classes(mod):
    out = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if (issubclass(obj, bt.Strategy) and obj.__module__ == mod.__name__):
            out.append(obj)
    return out


def param_default(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return clean(v)
    return repr(v)


def describe(cls):
    params = []
    for name, default in cls.params._getitems():
        params.append({
            'name': name,
            'default': param_default(default),
            'type': type(default).__name__,
        })
    return {
        'name': cls.__name__,
        'doc': inspect.getdoc(cls) or '',
        'params': params,
    }


def coerce(value, default):
    '''Convert a UI-supplied value to the type of the parameter default'''
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)
    if isinstance(default, int):
        return int(float(value))
    if isinstance(default, float):
        return float(value)
    if isinstance(default, str):
        return str(value)
    if default is None and isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------
def load_dataframe(feed, fromdate, todate):
    import pandas as pd

    if feed['type'] == 'yahoo':
        import yfinance as yf
        df = yf.download(feed['ticker'], start=fromdate, end=todate,
                         interval=feed.get('interval') or '1d',
                         auto_adjust=False, progress=False)
        if df is None or df.empty:
            raise ValueError('Yahoo returned no data for %r' % feed['ticker'])
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    else:
        with open(feed['path']) as f:
            header = f.readline().strip().split(',')
            row = f.readline().strip().split(',')
        names = None
        # some backtrader sample files carry an unlabeled time column
        if len(row) == len(header) + 1 and ':' in row[1]:
            names = header[:1] + ['Time'] + header[1:]
        df = pd.read_csv(feed['path'], header=0, names=names)
        cols = {c.lower().strip(): c for c in df.columns}
        if 'datetime' in cols:
            idx = pd.to_datetime(df[cols['datetime']])
        elif 'date' in cols and 'time' in cols:
            idx = pd.to_datetime(df[cols['date']].astype(str) + ' ' +
                                 df[cols['time']].astype(str))
        elif 'date' in cols:
            idx = pd.to_datetime(df[cols['date']])
        else:
            raise ValueError('CSV needs a Date or Datetime column')
        df.index = idx
        df = df.sort_index()

    df.columns = [str(c).lower().strip() for c in df.columns]
    missing = [c for c in ('open', 'high', 'low', 'close') if c not in df]
    if missing:
        raise ValueError('Data feed is missing columns: %s' % missing)
    if 'volume' not in df:
        df['volume'] = 0
    if 'openinterest' not in df:
        df['openinterest'] = 0

    if feed['type'] != 'yahoo':
        if fromdate:
            df = df[df.index >= pd.Timestamp(fromdate)]
        if todate:
            df = df[df.index <= pd.Timestamp(todate) + pd.Timedelta(days=1)]

    df = df[['open', 'high', 'low', 'close', 'volume', 'openinterest']]
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    if df.empty:
        raise ValueError('No bars in the selected date range')
    return df


# --------------------------------------------------------------------------
# recorder analyzer: captures bars, equity, orders and trades for the UI
# --------------------------------------------------------------------------
class Recorder(bt.Analyzer):
    def start(self):
        self.bars = []
        self.equity = []
        self.orders = []
        self.trades = {}

    def next(self):
        d = self.strategy.datas[0]
        t = ts(d.datetime.datetime(0))
        self.bars.append({
            'time': t, 'open': clean(d.open[0]), 'high': clean(d.high[0]),
            'low': clean(d.low[0]), 'close': clean(d.close[0]),
            'volume': clean(d.volume[0]),
        })
        self.equity.append({
            'time': t,
            'value': clean(self.strategy.broker.getvalue()),
            'cash': clean(self.strategy.broker.getcash()),
            'position': self.strategy.getposition(d).size,
        })

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        rec = {
            'ref': order.ref,
            'side': 'BUY' if order.isbuy() else 'SELL',
            'type': order.getordername(),
            'status': order.getstatusname(),
            'created': ts(bt.num2date(order.created.dt)),
            'size': order.created.size,
        }
        if order.status == order.Completed:
            rec.update({
                'time': ts(bt.num2date(order.executed.dt)),
                'price': clean(order.executed.price),
                'size': order.executed.size,
                'value': clean(order.executed.value),
                'comm': clean(order.executed.comm),
            })
        self.orders.append(rec)

    def notify_trade(self, trade):
        t = self.trades.setdefault(trade.ref, {'ref': trade.ref})
        if trade.justopened:
            t.update({
                'opened': ts(bt.num2date(trade.dtopen)),
                'size': trade.size,
                'price': clean(trade.price),
                'direction': 'LONG' if trade.size > 0 else 'SHORT',
            })
        if trade.isclosed:
            t.update({
                'closed': ts(bt.num2date(trade.dtclose)),
                'bars': trade.barlen,
                'pnl': clean(trade.pnl),
                'pnlcomm': clean(trade.pnlcomm),
            })

    def get_analysis(self):
        return {}


def indicator_series(strat, nbars, times):
    '''Export the strategy's own indicators so the UI can draw them'''
    out = []
    for ind in strat.getindicators():
        if not ind.plotinfo.plot:
            continue
        try:
            name = ind.plotlabel()
        except Exception:
            name = ind.plotinfo.plotname or ind.__class__.__name__
        overlay = not ind.plotinfo.subplot
        lines = []
        for i in range(ind.size()):
            alias = ind.lines._getlinealias(i)
            arr = list(ind.lines[i].array)[-nbars:]
            pad = [None] * (nbars - len(arr))
            vals = pad + [clean(float(v)) if v is not None else None
                          for v in arr]
            lines.append({
                'name': alias,
                'data': [{'time': t, 'value': v}
                         for t, v in zip(times, vals) if v is not None],
            })
        out.append({'name': name, 'overlay': overlay, 'lines': lines})
    return out


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_inspect(path):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mod = load_module(path)
        emit({'ok': True, 'classes': [describe(c)
                                      for c in strategy_classes(mod)]})
    except Exception:
        emit({'ok': False, 'error': traceback.format_exc(limit=6)})


def cmd_run(cfg):
    logbuf = io.StringIO()
    try:
        with contextlib.redirect_stdout(logbuf):
            result = run_backtest(cfg)
        log = logbuf.getvalue()
        result['log'] = log[-200000:]
        result['logTruncated'] = len(log) > 200000
        result['ok'] = True
        emit(result)
    except Exception:
        emit({'ok': False, 'error': traceback.format_exc(limit=8),
              'log': logbuf.getvalue()[-50000:]})


def run_backtest(cfg):
    mod = load_module(cfg['strategyFile'])
    classes = strategy_classes(mod)
    if not classes:
        raise ValueError('No bt.Strategy subclass found in strategy file')
    cls = classes[0]
    if cfg.get('strategyClass'):
        match = [c for c in classes if c.__name__ == cfg['strategyClass']]
        if not match:
            raise ValueError('Class %s not found' % cfg['strategyClass'])
        cls = match[0]

    defaults = dict(cls.params._getitems())
    params = {}
    for k, v in (cfg.get('params') or {}).items():
        if k in defaults and v not in (None, ''):
            params[k] = coerce(v, defaults[k])

    df = load_dataframe(cfg['feed'], cfg.get('fromdate'), cfg.get('todate'))

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.adddata(bt.feeds.PandasData(dataname=df),
                    name=cfg.get('feedName') or 'data0')
    cerebro.addstrategy(cls, **params)

    cash = float(cfg.get('cash') or 100000)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(
        commission=float(cfg.get('commission') or 0) / 100.0)
    slip = float(cfg.get('slippage') or 0)
    if slip:
        cerebro.broker.set_slippage_perc(slip / 100.0)
    if cfg.get('coc'):
        cerebro.broker.set_coc(True)

    sizer = cfg.get('sizer') or {}
    if sizer.get('type') == 'percent':
        cerebro.addsizer(bt.sizers.PercentSizerInt,
                         percents=float(sizer.get('value') or 95))
    else:
        cerebro.addsizer(bt.sizers.FixedSize,
                         stake=int(float(sizer.get('value') or 1)))

    cerebro.addanalyzer(Recorder, _name='rec')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                        timeframe=bt.TimeFrame.Days, annualize=True,
                        riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='ret')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

    started = datetime.now()
    strat = cerebro.run()[0]
    elapsed = (datetime.now() - started).total_seconds()

    rec = strat.analyzers.rec
    ta = strat.analyzers.ta.get_analysis()
    dd = strat.analyzers.dd.get_analysis()
    ret = strat.analyzers.ret.get_analysis()

    def g(d, *keys):
        for k in keys:
            try:
                d = d[k]
            except (KeyError, TypeError):
                return None
        return d

    final = cerebro.broker.getvalue()
    closed = g(ta, 'total', 'closed') or 0
    won = g(ta, 'won', 'total') or 0
    first_close = rec.bars[0]['close'] if rec.bars else None
    last_close = rec.bars[-1]['close'] if rec.bars else None

    metrics = {
        'startCash': cash,
        'finalValue': clean(final),
        'pnl': clean(final - cash),
        'totalReturnPct': clean((final / cash - 1) * 100),
        'annualReturnPct': clean((ret.get('rnorm100'))),
        'buyHoldReturnPct': clean((last_close / first_close - 1) * 100)
        if first_close else None,
        'sharpe': clean(strat.analyzers.sharpe.get_analysis()
                        .get('sharperatio')),
        'maxDrawdownPct': clean(g(dd, 'max', 'drawdown')),
        'maxDrawdownLen': g(dd, 'max', 'len'),
        'sqn': clean(strat.analyzers.sqn.get_analysis().get('sqn')),
        'trades': closed,
        'openTrades': g(ta, 'total', 'open') or 0,
        'won': won,
        'lost': g(ta, 'lost', 'total') or 0,
        'winRatePct': clean(won / closed * 100) if closed else None,
        'avgWin': clean(g(ta, 'won', 'pnl', 'average')),
        'avgLoss': clean(g(ta, 'lost', 'pnl', 'average')),
        'bars': len(rec.bars),
        'elapsedSec': elapsed,
    }

    times = [b['time'] for b in rec.bars]
    benchmark = []
    if first_close:
        benchmark = [{'time': b['time'],
                      'value': clean(cash * b['close'] / first_close)}
                     for b in rec.bars]

    return {
        'strategy': cls.__name__,
        'params': {k: param_default(v)
                   for k, v in strat.params._getkwargs().items()},
        'metrics': metrics,
        'bars': rec.bars,
        'equity': rec.equity,
        'benchmark': benchmark,
        'orders': rec.orders,
        'trades': sorted(rec.trades.values(), key=lambda t: t['ref']),
        'indicators': indicator_series(strat, len(times), times),
    }


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'inspect':
        cmd_inspect(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == 'run':
        cmd_run(json.loads(sys.stdin.read()))
    else:
        sys.stderr.write(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
