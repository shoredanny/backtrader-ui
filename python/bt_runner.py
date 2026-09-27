#!/usr/bin/env python
'''Bridge between the Node.js UI and backtrader.

Usage:
  bt_runner.py inspect <file.py> [<file.py> ...]  -> JSON map path -> info
  bt_runner.py run                                -> JSON config on stdin,
                                                     JSON results on stdout

Strategy files may declare (all optional, module level):

  DEFAULTS = dict(feed='orcl-1995-2014.txt' | 'yahoo:TICKER[:interval]',
                  fromdate='YYYY-MM-DD', todate='YYYY-MM-DD', cash=100000,
                  commission=0.0, slippage=0.0, coc=False,
                  sizer=dict(type='fixed'|'percent', value=1))
      Form values the UI pre-selects when the strategy is chosen.

  OPTIONS = dict(name=default, ...)
      Extra run settings shown in the UI, passed to configure() as ctx.opts.

  CHOICES = dict(name=[value, ...], ...)
      Allowed values for a param or option (rendered as a dropdown).

  def configure(cerebro, data, ctx):
      Called before the run, after the broker and sizer from the form are set
      (so it may override them). `data` is the feed selected in the UI. If
      configure adds no data feed, the runner adds `data` itself. ctx has:
        ctx.opts        the OPTIONS values chosen in the UI
        ctx.fromdate    datetime.date or None
        ctx.todate      datetime.date or None
        ctx.load(src, **kwargs)   another feed: file name in backtrader/datas
                                  (or uploads) or 'yahoo:TICKER'
        ctx.make_data(**kwargs)   a fresh copy of the selected feed, with
                                  feed params overridden (timeframe, ...)
        ctx.datapath(name)        absolute path of a backtrader/datas file
'''
import bisect
import calendar
import contextlib
import datetime
import importlib.util
import inspect
import io
import json
import math
import os
import statistics
import sys
import traceback
import types
import uuid

# Prefer the backtrader source checkout (with local modifications) over the
# copy installed in site-packages
BT_ROOT = os.environ.get('BT_ROOT')
if BT_ROOT:
    sys.path.insert(0, BT_ROOT)

import backtrader as bt  # noqa: E402

BT_DATAS = os.path.join(BT_ROOT or '', 'datas')
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data', 'uploads')
UI_ANALYZERS = ('ui_rec', 'ui_sharpe', 'ui_dd', 'ui_ret', 'ui_ta', 'ui_sqn')
# observers already represented elsewhere in the UI
SKIP_OBSERVERS = (bt.observers.BuySell, bt.observers.Trades,
                  bt.observers.Broker, bt.observers.Cash, bt.observers.Value)
MAX_SERIES_POINTS = 20000


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


def jsonable(o, depth=0):
    '''Convert analyzer output (nested OrderedDicts with datetime keys) to
    JSON-safe structures'''
    if depth > 8:
        return str(o)
    if isinstance(o, dict):
        items = list(o.items())
        out = {}
        for k, v in items[:5000]:
            if isinstance(k, (datetime.date, datetime.datetime)):
                k = k.isoformat()
            out[str(k)] = jsonable(v, depth + 1)
        if len(items) > 5000:
            out['…'] = '%d more entries' % (len(items) - 5000)
        return out
    if isinstance(o, (list, tuple)):
        return [jsonable(x, depth + 1) for x in o[:5000]]
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, int):
        return o
    if isinstance(o, float):
        return clean(o)
    if isinstance(o, (datetime.date, datetime.datetime, datetime.time)):
        return o.isoformat()
    try:
        f = float(o)  # numpy scalars
        return clean(f)
    except (TypeError, ValueError):
        return str(o)


@contextlib.contextmanager
def strategy_dir_on_path(path):
    '''Let a strategy import helper modules that live next to it'''
    d = os.path.dirname(os.path.abspath(path))
    sys.path.insert(0, d)
    try:
        yield
    finally:
        try:
            sys.path.remove(d)
        except ValueError:
            pass


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
        if issubclass(obj, bt.Strategy) and obj.__module__ == mod.__name__:
            out.append(obj)
    # keep the order in which classes appear in the file
    def lineno(c):
        try:
            return inspect.getsourcelines(c)[1]
        except (OSError, TypeError):
            return 0
    out.sort(key=lineno)
    return out


def value_repr(v, mod=None):
    '''How a param/option default is shown in (and read back from) the UI'''
    if v is None or isinstance(v, (bool, int, float, str)):
        return clean(v)
    if inspect.isclass(v) or inspect.isfunction(v):
        for prefix, ns in (('bt.ind', bt.ind), ('bt.sizers', bt.sizers),
                           ('bt.analyzers', bt.analyzers),
                           ('bt.observers', bt.observers), ('bt', bt)):
            if getattr(ns, v.__name__, None) is v:
                return '%s.%s' % (prefix, v.__name__)
        if mod is not None and getattr(mod, v.__name__, None) is v:
            return v.__name__
        return '%s.%s' % (v.__module__, v.__qualname__)
    return repr(v)


def value_type(v):
    if v is None:
        return 'none'
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, int):
        return 'int'
    if isinstance(v, float):
        return 'float'
    if isinstance(v, str):
        return 'str'
    return 'expr'


def describe_values(items, mod):
    return [{'name': k, 'default': value_repr(v, mod), 'type': value_type(v)}
            for k, v in items]


def describe(cls, mod):
    return {
        'name': cls.__name__,
        'doc': inspect.getdoc(cls) or '',
        'params': describe_values(cls.params._getitems(), mod),
    }


def eval_ns(mod):
    ns = dict(vars(mod))
    ns.update(bt=bt, backtrader=bt, datetime=datetime, math=math)
    return ns


def coerce(value, default, ns, mod):
    '''Convert a UI-supplied value to the type of the default'''
    if isinstance(value, str) and value == str(value_repr(default, mod)):
        return default
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)
    if isinstance(default, (int, float)):
        try:
            num = float(value)
            return int(num) if isinstance(default, int) else num
        except (TypeError, ValueError):
            return eval(str(value), ns)  # e.g. bt.Order.StopTrail
    if isinstance(default, str):
        return str(value)
    if isinstance(value, str):
        if default is None and value.strip() in ('', 'None'):
            return None
        try:
            return json.loads(value)
        except ValueError:
            pass
        try:
            return eval(value, ns)
        except Exception:
            if default is None:
                return value
            raise
    return value


def coerce_all(supplied, defaults, ns, mod):
    out = {}
    for k, v in (supplied or {}).items():
        if k in defaults and v is not None and not (v == '' and
                                                     defaults[k] != ''):
            out[k] = coerce(v, defaults[k], ns, mod)
    return out


# --------------------------------------------------------------------------
# data feeds
# --------------------------------------------------------------------------
def sniff_csv(path, nrows=80):
    with open(path) as f:
        header = [h.strip() for h in f.readline().strip().split(',')]
        rows = []
        for line in f:
            line = line.strip()
            if line:
                rows.append(line.split(','))
            if len(rows) >= nrows:
                break
    return header, rows


def timeframe_from_times(times):
    '''Guess backtrader timeframe/compression from bar datetimes'''
    deltas = [(b - a).total_seconds() for a, b in zip(times, times[1:])
              if b > a]
    if not deltas:
        return bt.TimeFrame.Days, 1
    med = statistics.median(deltas)
    if med < 1:
        return bt.TimeFrame.Ticks, 1
    if med < 60:
        return bt.TimeFrame.Seconds, max(1, int(round(med)))
    if med < 86400 * 0.9:
        return bt.TimeFrame.Minutes, max(1, int(round(med / 60)))
    if med <= 86400 * 4:
        return bt.TimeFrame.Days, 1
    if med <= 86400 * 10:
        return bt.TimeFrame.Weeks, 1
    if med <= 86400 * 45:
        return bt.TimeFrame.Months, 1
    return bt.TimeFrame.Years, 1


def csv_kind(header, rows):
    lower = [h.lower() for h in header]
    if 'adj close' in lower:
        return 'yahoo'
    btcols = ['date', 'open', 'high', 'low', 'close', 'volume', 'openinterest']
    if lower in (btcols, btcols[:1] + ['time'] + btcols[1:]):
        return 'btcsv'
    return 'pandas'


def row_datetime(header, row):
    lower = [h.lower() for h in header]
    if 'datetime' in lower:
        return datetime.datetime.fromisoformat(row[lower.index('datetime')])
    d = datetime.datetime.fromisoformat(row[0][:10])
    # time either in a labeled column or an unlabeled 2nd field
    if ('time' in lower or len(row) == len(header) + 1) and ':' in row[1]:
        h, m, s = (row[1].split(':') + ['0', '0'])[:3]
        d = d.replace(hour=int(h), minute=int(m), second=int(float(s)))
    return d


def pandas_frame(feed, fromdate, todate):
    import pandas as pd

    if feed['type'] == 'yahoo':
        import yfinance as yf
        end = todate + datetime.timedelta(days=1) if todate else None
        df = yf.download(feed['ticker'], start=fromdate, end=end,
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
        header, rows = sniff_csv(feed['path'], 1)
        names = None
        if rows and len(rows[0]) == len(header) + 1 and ':' in rows[0][1]:
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
        if fromdate:
            df = df[df.index >= pd.Timestamp(fromdate)]
        if todate:
            df = df[df.index < pd.Timestamp(todate) + pd.Timedelta(days=1)]

    df.columns = [str(c).lower().strip() for c in df.columns]
    missing = [c for c in ('open', 'high', 'low', 'close') if c not in df]
    if missing:
        raise ValueError('Data feed is missing columns: %s' % missing)
    for c in ('volume', 'openinterest'):
        if c not in df:
            df[c] = 0
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    if df.empty:
        raise ValueError('No bars in the selected date range')
    return df


def make_feed(feed, fromdate=None, todate=None, pandas=False, **kwargs):
    '''Create a backtrader data feed for a UI feed spec. Local files use the
    native backtrader/Yahoo CSV feeds unless pandas=True (plain OHLCV-OI
    lines, e.g. to chain feeds of different formats)'''
    kw = dict(kwargs)
    if feed['type'] == 'file' and not pandas:
        path = feed['path']
        header, rows = sniff_csv(path)
        kind = csv_kind(header, rows)
        if kind in ('btcsv', 'yahoo'):
            if 'timeframe' not in kw:
                tf, comp = timeframe_from_times(
                    [row_datetime(header, r) for r in rows])
                kw.setdefault('timeframe', tf)
                kw.setdefault('compression', comp)
            if fromdate:
                kw.setdefault('fromdate', fromdate)
            if todate:
                kw.setdefault('todate', todate)
            cls = (bt.feeds.BacktraderCSVData if kind == 'btcsv'
                   else bt.feeds.YahooFinanceCSVData)
            return cls(dataname=path, **kw)

    df = pandas_frame(feed, fromdate, todate)
    if 'timeframe' not in kw:
        tf, comp = timeframe_from_times(list(df.index[:200].to_pydatetime()))
        kw.setdefault('timeframe', tf)
        kw.setdefault('compression', comp)
    return bt.feeds.PandasData(dataname=df, **kw)


def resolve_source(src):
    '''"yahoo:TICKER[:interval]" or a file name -> feed spec'''
    if src.startswith('yahoo:'):
        parts = src.split(':')
        return {'type': 'yahoo', 'ticker': parts[1],
                'interval': parts[2] if len(parts) > 2 else '1d'}
    for base in ('', BT_DATAS, UPLOADS):
        p = os.path.join(base, src) if base else src
        if os.path.isabs(p) and os.path.exists(p):
            return {'type': 'file', 'path': p}
    raise ValueError('Data file not found: %s' % src)


def parse_date(s):
    if not s:
        return None
    return datetime.date.fromisoformat(str(s)[:10])


class LazyFeedError(object):
    '''Stands in for the selected feed when it could not be loaded; raises
    the original error as soon as a configure() hook touches it'''
    def __init__(self, err):
        self._err = err

    def __getattr__(self, name):
        raise self._err


class Ctx(object):
    def __init__(self, feed, fromdate, todate, opts, feedname):
        self.feed = feed
        self.fromdate = fromdate
        self.todate = todate
        self.opts = types.SimpleNamespace(**opts)
        self._feedname = feedname

    def datapath(self, name):
        return os.path.join(BT_DATAS, name)

    def load(self, src, fromdate=None, todate=None, **kwargs):
        spec = resolve_source(src)
        kwargs.setdefault('name', os.path.splitext(os.path.basename(
            src.split(':')[1] if src.startswith('yahoo:') else src))[0])
        return make_feed(spec, fromdate or self.fromdate,
                         todate or self.todate, **kwargs)

    def make_data(self, **kwargs):
        kwargs.setdefault('name', self._feedname)
        return make_feed(self.feed, self.fromdate, self.todate, **kwargs)


# --------------------------------------------------------------------------
# recorder analyzer: captures bars, equity, orders and trades for the UI
# --------------------------------------------------------------------------
class Recorder(bt.Analyzer):
    def start(self):
        self.d = self.strategy.datas[0]
        self.daily = self.d._timeframe >= bt.TimeFrame.Days
        self.bars = []
        self.rawtimes = []  # unbumped, for mapping other series
        self.equity = []
        self.orders = []
        self.trades = {}
        self._lastlen = None

    def to_ts(self, dt):
        if self.daily:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return calendar.timegm(dt.timetuple())

    def num_ts(self, num):
        return self.to_ts(bt.num2date(num))

    def _line(self, name, fallback=True):
        line = getattr(self.d.lines, name, None)
        if line is None:
            if not fallback:
                return 0
            line = main_line(self.d)
        try:
            return clean(float(line[0]))
        except (TypeError, ValueError):
            return None

    def _possize(self, d):
        # positions.get: getposition() would create an entry and make the
        # broker value it, which fails for feeds without a close (bid/ask)
        pos = self.strategy.broker.positions.get(d)
        return pos.size if pos is not None else 0

    def next(self):
        d = self.d
        t = self.to_ts(d.datetime.datetime(0))
        close = self._line('close')
        bar = {'time': t, 'open': self._line('open'),
               'high': self._line('high'), 'low': self._line('low'),
               'close': close, 'volume': self._line('volume', False)}
        eq = {'time': t, 'value': clean(self.strategy.broker.getvalue()),
              'cash': clean(self.strategy.broker.getcash()),
              'position': self._possize(d)}
        n = len(d)
        if self.bars and n == self._lastlen:
            # replayed data: the current bar is still being built
            prev = self.bars[-2]['time'] if len(self.bars) > 1 else None
            if prev is not None and t <= prev:
                t = self.bars[-1]['time']
            bar['time'] = eq['time'] = t
            self.bars[-1], self.equity[-1] = bar, eq
            self.rawtimes[-1] = self.to_ts(d.datetime.datetime(0))
        else:
            if self.bars and t <= self.bars[-1]['time']:
                # e.g. several renko bricks on the same day
                t = self.bars[-1]['time'] + 1
            bar['time'] = eq['time'] = t
            self.bars.append(bar)
            self.equity.append(eq)
            self.rawtimes.append(self.to_ts(d.datetime.datetime(0)))
        self._lastlen = n

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        rec = {
            'ref': order.ref,
            'data': order.data._name or '',
            'main': order.data is self.d,
            'side': 'BUY' if order.isbuy() else 'SELL',
            'type': order.getordername(),
            'status': order.getstatusname(),
            'created': self.num_ts(order.created.dt),
            'size': order.created.size,
        }
        if order.status in (order.Completed, order.Partial):
            rec.update({
                'time': self.num_ts(order.executed.dt),
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
                'data': trade.data._name or '',
                'opened': self.num_ts(trade.dtopen),
                'size': trade.size,
                'price': clean(trade.price),
                'direction': 'LONG' if trade.size > 0 else 'SHORT',
            })
        if trade.isclosed:
            t.update({
                'closed': self.num_ts(trade.dtclose),
                'bars': trade.barlen,
                'pnl': clean(trade.pnl),
                'pnlcomm': clean(trade.pnlcomm),
            })

    def get_analysis(self):
        return {}


def main_line(d):
    '''close, or the first line of feeds without OHLC (e.g. bid/ask)'''
    line = getattr(d.lines, 'close', None)
    return line if line is not None else d.lines[0]


def clock_data(obj):
    '''The data feed that ultimately drives an indicator/observer'''
    seen = 0
    while obj is not None and not isinstance(obj, bt.AbstractDataBase):
        obj = getattr(obj, '_clock', None)
        seen += 1
        if seen > 20:
            return None
    return obj


def series_on_bars(rec, line, data):
    '''Values of a line aligned to the recorded main bars'''
    nbars = len(rec.bars)
    arr = list(line.array)
    try:
        n = len(line)
    except TypeError:
        n = len(arr)
    if 0 < n < len(arr):  # preallocated but never filled cells at the end
        arr = arr[:n]
    if not arr:
        return [None] * nbars
    if data is rec.d or data is None:
        arr = arr[-nbars:]
        vals = [None] * (nbars - len(arr)) + arr
    else:
        dts = list(data.datetime.array)[-len(arr):]
        arr = arr[-len(dts):]
        vals = [None] * nbars
        for num, v in zip(dts, arr):
            i = bisect.bisect_right(rec.rawtimes, rec.num_ts(num)) - 1
            if 0 <= i < nbars:
                vals[i] = v
    out = []
    for v in vals:
        try:
            out.append(clean(float(v)) if v is not None else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


def export_group(rec, obj, name, overlay, lines):
    times = [b['time'] for b in rec.bars]
    data = clock_data(obj)
    out_lines = []
    for label, line in lines:
        vals = series_on_bars(rec, line, data)
        pts = [{'time': t, 'value': v} for t, v in zip(times, vals)
               if v is not None]
        if not pts:
            continue
        if len(pts) > MAX_SERIES_POINTS:
            pts = pts[-MAX_SERIES_POINTS:]
        out_lines.append({'name': label, 'data': pts,
                          'sparse': len(pts) < 0.3 * max(len(times), 1)})
    if not out_lines:
        return None
    if data is not None and data is not rec.d:
        # computed on another data: own panel, labeled with that data
        overlay = False
        if not isinstance(obj, bt.AbstractDataBase):
            name = '%s · %s' % (name, data_label(data, rec))
    return {'name': name, 'overlay': overlay, 'lines': out_lines}


def data_label(d, rec):
    '''Name of a data; unnamed resampled/replayed copies get the timeframe'''
    if d._name:
        return d._name
    tf = bt.TimeFrame.getname(d._timeframe, d._compression)
    comp = '%d ' % d._compression if d._compression > 1 else ''
    return '%s (%s%s)' % (rec.d._name or 'data', comp, tf)


def plot_label(obj):
    try:
        return obj.plotlabel()
    except Exception:
        return obj.plotinfo.plotname or obj.__class__.__name__


def export_series(strat, rec):
    groups = []
    for ind in strat.getindicators():
        # skip bare lines operations (e.g. close - sma) and hidden ones
        plotinfo = getattr(ind, 'plotinfo', None)
        if plotinfo is None or not plotinfo.plot:
            continue
        g = export_group(rec, ind, plot_label(ind), not ind.plotinfo.subplot,
                         [(ind.lines._getlinealias(i), ind.lines[i])
                          for i in range(ind.size())])
        if g:
            groups.append(g)
    for obs in strat.getobservers():
        if type(obs) in SKIP_OBSERVERS or not obs.plotinfo.plot:
            continue
        g = export_group(rec, obs, plot_label(obs), False,
                         [(obs.lines._getlinealias(i), obs.lines[i])
                          for i in range(obs.size())])
        if g:
            g['kind'] = 'observer'
            groups.append(g)
    for i, d in enumerate(strat.datas[1:6], start=1):
        line = main_line(d)
        g = export_group(rec, d, 'Data%d: %s' % (i, data_label(d, rec)), False,
                         [('close', line)])
        if g:
            g['kind'] = 'data'
            groups.append(g)
    return groups


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def inspect_file(path):
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                strategy_dir_on_path(path):
            mod = load_module(path)
        options = getattr(mod, 'OPTIONS', None) or {}
        return {
            'ok': True,
            'doc': inspect.getdoc(mod) or '',
            'classes': [describe(c, mod) for c in strategy_classes(mod)],
            'defaults': jsonable(getattr(mod, 'DEFAULTS', None) or {}),
            'options': describe_values(options.items(), mod),
            'choices': jsonable(getattr(mod, 'CHOICES', None) or {}),
        }
    except BaseException:
        return {'ok': False, 'error': traceback.format_exc(limit=6)}


def cmd_inspect(paths):
    emit({'ok': True, 'results': {p: inspect_file(p) for p in paths}})


def cmd_run(cfg):
    logbuf = io.StringIO()
    try:
        with contextlib.redirect_stdout(logbuf), \
                strategy_dir_on_path(cfg['strategyFile']):
            result = run_backtest(cfg)
        log = logbuf.getvalue()
        result['log'] = log[-300000:]
        result['logTruncated'] = len(log) > 300000
        result['ok'] = True
        emit(result)
    except BaseException:
        emit({'ok': False, 'error': traceback.format_exc(limit=10),
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

    ns = eval_ns(mod)
    params = coerce_all(cfg.get('params'), dict(cls.params._getitems()),
                        ns, mod)
    optdefaults = dict(getattr(mod, 'OPTIONS', None) or {})
    opts = dict(optdefaults)
    opts.update(coerce_all(cfg.get('options'), optdefaults, ns, mod))

    fromdate = parse_date(cfg.get('fromdate'))
    todate = parse_date(cfg.get('todate'))
    feedname = cfg.get('feedName') or 'data0'

    cerebro = bt.Cerebro(stdstats=False)
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

    # a configure() hook may build its own feeds and never use this one, so
    # only fail on a bad selection if the feed is actually needed
    try:
        data, dataerr = make_feed(cfg['feed'], fromdate, todate,
                                  name=feedname), None
    except Exception as e:
        data, dataerr = None, e
    configure = getattr(mod, 'configure', None)
    if callable(configure):
        if data is None and dataerr is not None:
            data = LazyFeedError(dataerr)
        configure(cerebro, data, Ctx(cfg['feed'], fromdate, todate, opts,
                                     feedname))
    if not cerebro.datas:
        if dataerr is not None:
            raise dataerr
        cerebro.adddata(data)

    # the selected strategy goes first: configure() may add companions and
    # results/analyzers are read from the first strategy
    cerebro.strats.insert(0, [(cls, (), params)])
    cerebro.addanalyzer(Recorder, _name='ui_rec')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='ui_sharpe',
                        timeframe=bt.TimeFrame.Days, annualize=True,
                        riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='ui_dd')
    # backtrader's timeframe analyzers break below Seconds (ticks)
    cerebro.addanalyzer(bt.analyzers.Returns, _name='ui_ret',
                        timeframe=max(cerebro.datas[0]._timeframe,
                                      bt.TimeFrame.Seconds),
                        compression=cerebro.datas[0]._compression)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ui_ta')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='ui_sqn')

    started = datetime.datetime.now()
    strat = cerebro.run()[0]
    elapsed = (datetime.datetime.now() - started).total_seconds()

    an = strat.analyzers
    rec = an.getbyname('ui_rec')
    ta = an.getbyname('ui_ta').get_analysis()
    dd = an.getbyname('ui_dd').get_analysis()
    ret = an.getbyname('ui_ret').get_analysis()

    def g(d, *keys):
        for k in keys:
            try:
                d = d[k]
            except (KeyError, TypeError):
                return None
        return d

    final = cerebro.broker.getvalue()
    startcash = cerebro.broker.startingcash
    closed = g(ta, 'total', 'closed') or 0
    won = g(ta, 'won', 'total') or 0
    closes = [b['close'] for b in rec.bars if b['close']]
    first_close = closes[0] if closes else None
    last_close = closes[-1] if closes else None

    metrics = {
        'startCash': startcash,
        'finalValue': clean(final),
        'pnl': clean(final - startcash),
        'totalReturnPct': clean((final / startcash - 1) * 100)
        if startcash else None,
        'annualReturnPct': clean(ret.get('rnorm100')),
        'buyHoldReturnPct': clean((last_close / first_close - 1) * 100)
        if first_close else None,
        'sharpe': clean(an.getbyname('ui_sharpe').get_analysis()
                        .get('sharperatio')),
        'maxDrawdownPct': clean(g(dd, 'max', 'drawdown')),
        'maxDrawdownLen': g(dd, 'max', 'len'),
        'sqn': clean(an.getbyname('ui_sqn').get_analysis().get('sqn')),
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

    benchmark = []
    if first_close:
        benchmark = [{'time': b['time'],
                      'value': clean(startcash * b['close'] / first_close)}
                     for b in rec.bars if b['close']]

    analyzers = []
    for name, a in an.getitems():
        if name in UI_ANALYZERS:
            continue
        try:
            analysis = jsonable(a.get_analysis())
        except Exception as e:
            analysis = 'error: %s' % e
        analyzers.append({'name': name, 'type': a.__class__.__name__,
                          'analysis': analysis})

    return {
        'strategy': cls.__name__,
        'params': {k: value_repr(v, mod)
                   for k, v in strat.params._getkwargs().items()},
        'options': {k: value_repr(v, mod) for k, v in opts.items()},
        'mainData': rec.d._name or '',
        'metrics': metrics,
        'bars': rec.bars,
        'equity': rec.equity,
        'benchmark': benchmark,
        'orders': rec.orders,
        'trades': sorted(rec.trades.values(), key=lambda t: t['ref']),
        'indicators': export_series(strat, rec),
        'analyzers': analyzers,
    }


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'inspect':
        cmd_inspect(sys.argv[2:])
    elif len(sys.argv) >= 2 and sys.argv[1] == 'run':
        cmd_run(json.loads(sys.stdin.read()))
    else:
        sys.stderr.write(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
