#!/usr/bin/env python3
'''Usage: python3 tools/port_samples.py

Port backtrader/samples/**.py into Backtrader Studio strategy files.

For every sample the class/indicator/observer code is kept verbatim; the
command line handling (argparse, runstrat(), __main__) is removed and replaced
by a "Backtrader Studio setup" section (DEFAULTS / OPTIONS / CHOICES /
configure) that reproduces what runstrat() did.
'''
import ast
import os
import re
import sys

SAMPLES = os.path.expanduser('~/Project/backtrader/samples')
OUT = os.path.expanduser('~/Project/backtrader-ui/strategies')

DROP_FUNCS = {'runstrat', 'runstrategy', 'parse_args', 'run', 'getdata'}


def lit(v):
    return repr(v)


def dict_lit(name, d):
    if not d:
        return ''
    body = ''.join('    %s=%s,\n' % (k, lit(v)) for k, v in d.items())
    return '%s = dict(\n%s)\n' % (name, body)


def defaults(feed, fromdate='', todate='', cash=10000.0, commission=0.0,
             stake=1, coc=False, **extra):
    d = dict(feed=feed, fromdate=fromdate, todate=todate, cash=cash,
             commission=commission, slippage=0.0, coc=coc,
             sizer=dict(type='fixed', value=stake))
    d.update(extra)
    return d


WRITER = '''    if ctx.opts.writer:
        cerebro.addwriter(bt.WriterFile, csv=ctx.opts.wrcsv)
'''

SPECS = {}

# ---------------------------------------------------------------------------
SPECS['analyzer-annualreturn/analyzer-annualreturn.py'] = dict(
    doc='''SMA crossover long/short strategy used to showcase the return
analyzers: SQN, TimeReturn (or the legacy AnnualReturn), SharpeRatio and
TradeAnalyzer, plus a WriterFile summary in the Log tab.

The sample trades a futures-like asset (commission 2 per contract,
multiplier 10, margin 2000); change that in the sample options.''',
    defaults=defaults('2005-2006-day-001.txt', '2005-01-01', '2006-12-31',
                      cash=100000.0),
    options=dict(comm=2.0, mult=10, margin=2000.0, tframe='years',
                 legacyannual=False, writer=True, wrcsv=False),
    choices=dict(tframe=['days', 'weeks', 'months', 'years']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    cerebro.broker.setcommission(commission=o.comm, mult=o.mult,
                                 margin=o.margin)
    tframes = dict(days=bt.TimeFrame.Days, weeks=bt.TimeFrame.Weeks,
                   months=bt.TimeFrame.Months, years=bt.TimeFrame.Years)
    cerebro.addanalyzer(SQN)
    if o.legacyannual:
        cerebro.addanalyzer(AnnualReturn)
        cerebro.addanalyzer(SharpeRatio, legacyannual=True)
    else:
        cerebro.addanalyzer(TimeReturn, timeframe=tframes[o.tframe])
        cerebro.addanalyzer(SharpeRatio, timeframe=tframes[o.tframe])
    cerebro.addanalyzer(TradeAnalyzer)
    if o.writer:
        cerebro.addwriter(bt.WriterFile, csv=o.wrcsv, rounding=4)
''')

SPECS['bidask-to-ohlc/bidask-to-ohlc.py'] = dict(
    doc='''Turns bid/ask ticks into OHLC bars: a GenericCSVData maps the
"offer" column to open/high/low/close and resampledata() compresses ticks.

Uses its own data file (option "data", from backtrader/datas); the data feed
and dates selected in the form are ignored. Output is in the Log tab.''',
    defaults=defaults('2006-day-001.txt'),
    options=dict(data='bidask2.csv', compression=2),
    configure='''    o = ctx.opts
    bidask = btfeeds.GenericCSVData(
        dataname=ctx.datapath(o.data),
        dtformat='%d/%m/%y',
        time=1,  # position of time
        open=5, high=5, low=5, close=5,
        volume=7,
        openinterest=-1,  # -1 for not present
        timeframe=bt.TimeFrame.Ticks)
    cerebro.resampledata(bidask, timeframe=bt.TimeFrame.Ticks,
                         compression=o.compression)
''')

SPECS['bracket/bracket.py'] = dict(
    doc='''Bracket orders: on an MA crossover enter with a limit buy plus a
stop-loss and a take-profit sell as its children, either built by hand
(transmit=False / parent=...) or with buy_bracket (usebracket). See the order
notifications in the Log tab.''',
    defaults=defaults('2005-2006-day-001.txt'),
)

SPECS['btfd/btfd.py'] = dict(
    doc='''"Buy the f... dip": enter when the bar falls more than `fall`
(measured with `approach`), hold for `hold` bars, trading with 2x leverage
and cheat-on-close. The ValueUnlever observer shows the leveraged value and
the unleveraged asset curve.''',
    defaults=defaults('yahoo:^GSPC', '1990-01-01', '2016-10-01',
                      cash=100000.0, coc=True),
    options=dict(leverage=2.0, assetstart=100000.0),
    choices=dict(approach=['closeclose', 'openclose', 'highclose',
                           'highlow']),
    configure='''    cerebro.adddata(data)
    cerebro.broker.set_coc(True)
    cerebro.broker.setcommission(leverage=ctx.opts.leverage)
    cerebro.addobserver(ValueUnlever, assetstart=ctx.opts.assetstart)
''')

SPECS['calendar-days/calendar-days.py'] = dict(
    doc='''CalendarDays filter: fills the gaps of a daily feed so that every
calendar day (weekends and holidays included) has a bar. Enable the filter
with the "calendar" option and look at the chart/log.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy (the sample adds no trading logic). The optional
    SMA shows how indicators behave over the filled days.\'\'\'
    params = dict(sma=False, period=15)

    def __init__(self):
        if self.p.sma:
            btind.SMA(period=self.p.period)
''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31'),
    options=dict(calendar=False, fprice=None, fvol=0.0, writer=False,
                 wrcsv=False),
    configure='''    o = ctx.opts
    if o.calendar:
        # backtrader's filter compares fill_price > 0, which fails for None
        # on Python 3; 0 means the same: fill with the last close
        fprice = float(o.fprice) if o.fprice is not None else 0
        data.addfilter(btfilters.CalendarDays,
                       fill_price=fprice, fill_vol=o.fvol)
    cerebro.adddata(data)
''' + WRITER)

SPECS['calmar/calmar-test.py'] = dict(
    doc='''SMA 15/50 crossover (long only) evaluated with the Calmar
analyzer (see the Analyzers tab).''',
    defaults=defaults('orcl-1995-2014.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.addanalyzer(bt.analyzers.Calmar)
''')

SPECS['cheat-on-open/cheat-on-open.py'] = dict(
    doc='''Cheat-on-open: with the option enabled the strategy decides in
next_open() and its market orders are filled at the open of the same bar
instead of the next one. Compare the fills in the Log tab with it on/off.''',
    defaults=defaults('2005-2006-day-001.txt'),
    options=dict(cheat_on_open=False),
    configure='''    cerebro.adddata(data)
    cerebro.p.cheat_on_open = ctx.opts.cheat_on_open
''')

SPECS['commission-schemes/commission-schemes.py'] = dict(
    doc='''SMA crossover used to compare commission schemes: futures-like
(fixed per contract with margin and multiplier) versus stock-like
percentage commissions. Tune them in the sample options.''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31'),
    options=dict(comm=2.0, mult=10, margin=2000.0, commtype='none',
                 stocklike=False, percrel=False),
    choices=dict(commtype=['none', 'perc', 'fixed']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    commtypes = dict(none=None, perc=bt.CommInfoBase.COMM_PERC,
                     fixed=bt.CommInfoBase.COMM_FIXED)
    cerebro.broker.setcommission(commission=o.comm, mult=o.mult,
                                 margin=o.margin, percabs=not o.percrel,
                                 commtype=commtypes[o.commtype],
                                 stocklike=o.stocklike)
''')

SPECS['credit-interest/credit-interest.py'] = dict(
    doc='''Credit interest charged on short (and optionally long) positions.
A signal strategy goes long/short on an SMA crossover; set the yearly
interest rate in the sample options and compare the P&L.''',
    replace=[('''class St(bt.SignalStrategy):
    opcounter = itertools.count(1)
''', '''class St(bt.SignalStrategy):
    # Backtrader Studio: the signals were added with cerebro.add_signal in
    # the sample; they are created here from the params instead
    params = dict(period1=10, period2=30, signal='longshort', no_exit=False)

    opcounter = itertools.count(1)

    def __init__(self):
        sigtype = dict(longshort=bt.signal.SIGNAL_LONGSHORT,
                       long=bt.signal.SIGNAL_LONG,
                       short=bt.signal.SIGNAL_SHORT)[self.p.signal]
        self.signal_add(sigtype, SMACrossOver(p1=self.p.period1,
                                              p2=self.p.period2))
        if self.p.no_exit:
            if self.p.signal == 'long':
                self.signal_add(bt.signal.SIGNAL_LONGEXIT, NoExit())
            elif self.p.signal == 'short':
                self.signal_add(bt.signal.SIGNAL_SHORTEXIT, NoExit())
''')],
    defaults=defaults('2005-2006-day-001.txt', cash=50000.0, stake=10),
    options=dict(interest=0.0, interest_long=False, int2pnl=True,
                 stocklike=False, margin=0.0, mult=1.0),
    choices=dict(signal=['longshort', 'long', 'short']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    cerebro.broker.set_int2pnl(o.int2pnl)
    comminfo = bt.CommissionInfo(mult=o.mult, margin=o.margin,
                                 stocklike=o.stocklike, interest=o.interest,
                                 interest_long=o.interest_long)
    cerebro.broker.addcommissioninfo(comminfo)
''')

SPECS['data-bid-ask/bidask.py'] = dict(
    doc='''A data feed with a custom line hierarchy (bid/ask instead of OHLC)
and a strategy printing it. Uses its own file (option "data"); the selected
data feed and dates are ignored. The chart shows the bid line.''',
    defaults=defaults('2006-day-001.txt', params=dict(period=5)),
    options=dict(data='bidask.csv', dtformat='%m/%d/%Y %H:%M:%S'),
    configure='''    o = ctx.opts
    cerebro.adddata(BidAskCSV(dataname=ctx.datapath(o.data),
                              dtformat=o.dtformat,
                              timeframe=bt.TimeFrame.Ticks))
''')

SPECS['data-filler/data-filler.py'] = dict(
    doc='''SessionFilter / SessionFiller: drop bars outside the trading
session and fill missing minute bars inside it. The optional RelativeVolume
indicator (relativevolume.py) compares each bar's volume with the same
moment of the previous session.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample is about the data filters\'\'\'
''',
    defaults=defaults('2006-01-02-volume-min-001.txt', '2006-01-01',
                      '2006-12-31'),
    options=dict(filter=False, filler=False, fvol=0.0, tstart='09:15',
                 tend='17:15', relvol=False, writer=False, wrcsv=False),
    configure='''    o = ctx.opts
    dtstart = datetime.datetime.strptime(o.tstart, '%H:%M')
    dtend = datetime.datetime.strptime(o.tend, '%H:%M')
    data = ctx.make_data(timeframe=bt.TimeFrame.Minutes, compression=1,
                         sessionstart=dtstart, sessionend=dtend)
    if o.filter:
        data.addfilter(btfilters.SessionFilter)
    if o.filler:
        data.addfilter(btfilters.SessionFiller, fill_vol=o.fvol)
    cerebro.adddata(data)
    if o.relvol:
        # + 1 to include last moment of the interval dstart <-> dtend
        td = ((dtend - dtstart).seconds // 60) + 1
        cerebro.addindicator(RelativeVolume, period=td,
                             volisnan=math.isnan(o.fvol))
''' + WRITER)

SPECS['data-multitimeframe/data-multitimeframe.py'] = dict(
    doc='''Two timeframes of the same data: the daily feed plus a weekly (or
monthly) version made by resampling or replaying it, each with its own SMA
and MACD. The strategy logs the length of both datas on every bar.''',
    defaults=defaults('2006-day-001.txt'),
    options=dict(timeframe='weekly', compression=1, replay=False,
                 noresample=False, dataname2='2006-week-001.txt',
                 runnext=False, nopreload=False, oldsync=False),
    choices=dict(timeframe=['daily', 'weekly', 'monthly']),
    configure='''    o = ctx.opts
    if o.noresample:
        data2 = ctx.load(o.dataname2)
    else:
        data2 = bt.DataClone(dataname=data)
        filters = dict(
            daily=(ReplayerDaily, ResamplerDaily),
            weekly=(ReplayerWeekly, ResamplerWeekly),
            monthly=(ReplayerMonthly, ResamplerMonthly))
        data2.addfilter(filters[o.timeframe][0 if o.replay else 1])
    cerebro.adddata(data)  # first the smaller timeframe
    cerebro.adddata(data2)  # and then the larger one
    cerebro.p.runonce = not o.runnext
    cerebro.p.preload = not o.nopreload
    cerebro.p.oldsync = o.oldsync
''')

SPECS['data-pandas/data-pandas-optix.py'] = dict(
    doc='''A PandasData subclass with extra lines (optix_close, optix_pess,
optix_opt) read from a DataFrame. Reads the selected file with pandas; it
needs the optix columns, as in 2006-day-001-optix.txt.''',
    defaults=defaults('2006-day-001-optix.txt'),
    options=dict(noheaders=False, noprint=False),
    configure='''    o = ctx.opts
    datapath = (ctx.feed['path'] if ctx.feed['type'] == 'file'
                else ctx.datapath('2006-day-001-optix.txt'))
    skiprows = 1 if o.noheaders else 0
    header = None if o.noheaders else 0
    dataframe = pandas.read_csv(datapath, skiprows=skiprows, header=header,
                                parse_dates=True, index_col=0)
    if not o.noprint:
        print('--------------------------------------------------')
        print(dataframe)
        print('--------------------------------------------------')
    cerebro.adddata(PandasDataOptix(dataname=dataframe))
''')

SPECS['data-pandas/data-pandas.py'] = dict(
    doc='''Loading a pandas DataFrame into backtrader with PandasData
(nocase=True matches the column names case-insensitively). The selected CSV
file is read with pandas and printed to the Log tab.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample is about the pandas data feed\'\'\'
''',
    defaults=defaults('2006-day-001.txt'),
    options=dict(noheaders=False, noprint=False),
    configure='''    o = ctx.opts
    datapath = (ctx.feed['path'] if ctx.feed['type'] == 'file'
                else ctx.datapath('2006-day-001.txt'))
    skiprows = 1 if o.noheaders else 0
    header = None if o.noheaders else 0
    dataframe = pandas.read_csv(datapath, skiprows=skiprows, header=header,
                                parse_dates=True, index_col=0)
    if not o.noprint:
        print('--------------------------------------------------')
        print(dataframe)
        print('--------------------------------------------------')
    cerebro.adddata(bt.feeds.PandasData(dataname=dataframe, nocase=True))
''')

SPECS['data-replay/data-replay.py'] = dict(
    doc='''Replaying a daily feed as weekly (or monthly) bars: the strategy
sees the larger bar being built day by day (len stays the same while the
counter increases).''',
    defaults=defaults('2006-day-001.txt'),
    options=dict(timeframe='weekly', compression=1),
    choices=dict(timeframe=['daily', 'weekly', 'monthly']),
    configure='''    o = ctx.opts
    tframes = dict(daily=bt.TimeFrame.Days, weekly=bt.TimeFrame.Weeks,
                   monthly=bt.TimeFrame.Months)
    data.replay(timeframe=tframes[o.timeframe], compression=o.compression)
    cerebro.adddata(data)
    cerebro.p.preload = False
''')

SPECS['data-resample/data-resample.py'] = dict(
    doc='''Resampling a daily feed to weekly or monthly bars with
cerebro.resampledata().''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample is about resampling\'\'\'
''',
    defaults=defaults('2006-day-001.txt'),
    options=dict(timeframe='weekly', compression=1),
    choices=dict(timeframe=['daily', 'weekly', 'monthly']),
    configure='''    o = ctx.opts
    tframes = dict(daily=bt.TimeFrame.Days, weekly=bt.TimeFrame.Weeks,
                   monthly=bt.TimeFrame.Months)
    cerebro.resampledata(data, timeframe=tframes[o.timeframe],
                         compression=o.compression)
''')

SPECS['daysteps/daysteps.py'] = dict(
    doc='''DayStepsFilter: every daily bar is delivered in two steps (the
open first, then the full bar), giving the strategy a chance to act at the
opening. See the Log tab.''',
    defaults=defaults('2005-2006-day-001.txt'),
    configure='''    data.addfilter(bt.filters.DayStepsFilter)
    cerebro.adddata(data)
    cerebro._doreplay = True
''')

SPECS['future-spot/future-spot.py'] = dict(
    doc='''Future/spot compensation: buy on data0 (the future) and sell on
data1 (a randomly altered copy acting as the spot), with data1 compensating
data0 so the P&L is booked against the future. Random entries: every run
differs.''',
    defaults=defaults('2006-day-001.txt', coc=True),
    options=dict(no_comp=False),
    configure='''    data0 = data
    cerebro.adddata(data0, name='data0')
    data1 = ctx.make_data(name='data1')
    data1.addfilter(close_changer)
    if not ctx.opts.no_comp:
        data1.compensate(data0)
    data1.plotinfo.plotmaster = data0
    cerebro.adddata(data1)
    cerebro.broker.set_coc(True)
''')

SPECS['gold-vs-sp500/gold-vs-sp500.py'] = dict(
    doc='''Gold vs the S&P 500: weekly moving averages of both plus their
rolling Pearson correlation and the LogReturns2 observer. data0 is the
selected feed (SPY by default) and data1 is downloaded from Yahoo (option
"data1").

scipy is not installed in the backtrader env, so the correlation falls back
to numpy.corrcoef (same result).''',
    replace=[('import scipy.stats\n', '''try:
    import scipy.stats
except ImportError:  # Backtrader Studio: numpy fallback for the correlation
    scipy = None
import numpy
'''), ('''        c, p = scipy.stats.pearsonr(self.data0.get(size=self.p.period),
                                    self.data1.get(size=self.p.period))
''', '''        x = self.data0.get(size=self.p.period)
        y = self.data1.get(size=self.p.period)
        if scipy is not None:
            c, p = scipy.stats.pearsonr(x, y)
        else:
            c = numpy.corrcoef(list(x), list(y))[0][1]
''')],
    defaults=defaults('yahoo:SPY', '2005-01-01', '2016-01-01'),
    options=dict(data1='GLD'),
    configure='''    data1 = ctx.load('yahoo:' + ctx.opts.data1)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks)
    cerebro.resampledata(data1, timeframe=bt.TimeFrame.Weeks)
    data1.plotinfo.plotmaster = data
    cerebro.addobserver(bt.observers.LogReturns2,
                        timeframe=bt.TimeFrame.Weeks, compression=20)
''')

SPECS['ib-cash-bid-ask/ib-cash-bid-ask.py'] = dict(
    doc='''Live Interactive Brokers sample: BID and ASK streams of a CASH
product (EUR.USD) resampled to 5 seconds, printed side by side.

Backtrader Studio runs historical data only, so both datas are the selected
feed (named BID and ASK). Run the original sample against TWS/IB Gateway for
the live behavior.''',
    drop=['ib_symbol', 'compression'],
    defaults=defaults('2006-min-005.txt'),
    configure='''    cerebro.adddata(data, name='BID')
    cerebro.adddata(ctx.make_data(name='ASK'))
''')

LIVE_NOTE = '''

Backtrader Studio runs this on historical data: the broker is the backtest
broker and, as no data ever turns LIVE, the param `backtest` (added in the
port) makes the strategy trade as if it were live. `trade` is enabled by
default in the form.'''

SPECS['ibtest/ibtest.py'] = dict(
    doc='''Interactive Brokers test strategy: logs every bar and, with
`trade`, enters with the configured order type (market, limit, stop trail,
bracket, OCA ...) and scales out.''' + LIVE_NOTE,
    replace=[('''        bracket=False,
    )
''', '''        bracket=False,
        backtest=True,  # Backtrader Studio: act as if data were live
    )
'''), ('''    def start(self):
        if self.data0.contractdetails is not None:''', '''    def start(self):
        if self.p.backtest:
            self.datastatus = 1
        if getattr(self.data0, 'contractdetails', None) is not None:''')],
    defaults=defaults('orcl-2014.txt', cash=100000.0,
                      params=dict(trade=True)),
)

SPECS['kselrsi/ksignal.py'] = dict(
    doc='''RSI signal strategy (after a post by Keith Selover): long when RSI
crosses up the lower band, short when it crosses down the upper band, exits
around the RSI mid level.''',
    defaults=defaults('yahoo:XOM', '2012-09-01', '2016-01-01',
                      cash=100000.0, stake=100),
)

SPECS['lineplotter/lineplotter.py'] = dict(
    doc='''LinePlotterIndicator: plot an arbitrary lines expression (high -
low, or a scaled mid price with `ondata`) as if it were an indicator.''',
    defaults=defaults('2005-2006-day-001.txt'),
)

SPECS['lrsi/lrsi-test.py'] = dict(
    doc='''Laguerre RSI on the mid price. The sample also used LaguerreRSI2
and LaguerreRSI3, which this backtrader version does not have; the
LaguerreFilter is shown instead.''',
    replace=[('''        bt.ind.LaguerreRSI3(mid)
        bt.ind.LaguerreRSI2(mid)
''', '''        # Backtrader Studio: LaguerreRSI3/LaguerreRSI2 do not exist in this
        # backtrader version
        bt.ind.LaguerreFilter(mid)
''')],
    defaults=defaults('2005-2006-day-001.txt'),
)

SPECS['macd-settings/macd-settings.py'] = dict(
    doc='''Van K. Tharp style MACD system: enter on a MACD/signal upward
cross while the SMA points down, exit with an ATR trailing stop. Sized with
the FixedPerc sizer (20% of cash), percentage stock commission and a set of
analyzers (TimeReturn, benchmark, Sharpe, SQN) plus the DrawDown observer.''',
    drop=['DATASETS'],
    defaults=defaults('yhoo-1996-2014.txt', '2005-01-01', cash=50000.0),
    options=dict(cashalloc=0.20, commperc=0.0033, riskfreerate=0.01),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    comminfo = bt.commissions.CommInfo_Stocks_Perc(commission=o.commperc,
                                                   percabs=True)
    cerebro.broker.addcommissioninfo(comminfo)
    cerebro.addsizer(FixedPerc, perc=o.cashalloc)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='alltime_roi',
                        timeframe=bt.TimeFrame.NoTimeFrame)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, data=data, _name='benchmark',
                        timeframe=bt.TimeFrame.NoTimeFrame)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Years,
                        riskfreerate=o.riskfreerate)
    cerebro.addanalyzer(bt.analyzers.SQN)
    cerebro.addobserver(bt.observers.DrawDown)
''')

SPECS['memory-savings/memory-savings.py'] = dict(
    doc='''Memory savings with exactbars: run a bunch of indicators and
report how many memory cells are used (see the end of the Log tab).
save: 0 = keep everything, 1 = minimum, -1/-2 = keep what plotting needs.''',
    defaults=defaults('yhoo-1996-2015.txt'),
    options=dict(save=0),
    choices=dict(save=[0, 1, -1, -2]),
    configure='''    cerebro.adddata(data)
    cerebro.p.runonce = False
    cerebro.p.exactbars = ctx.opts.save
''')

SPECS['mixing-timeframes/mixing-timeframes.py'] = dict(
    doc='''Mixing timeframes in one expression: daily closes compared with
monthly pivot point support levels. `multi` couples the monthly indicator to
the daily timeframe.''',
    defaults=defaults('2005-2006-day-001.txt', params=dict(multi=False)),
    configure='''    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Months)
    cerebro.p.runonce = False
''')

SPECS['multi-copy/multi-copy.py'] = dict(
    doc='''Two strategies (TheStrategy and TheStrategy2, with different
parameters) trading at the same time on the same data, or on a copy of it
(copydata). The selected class runs with the form's params; the other one is
added as its companion when "both" is enabled.''',
    defaults=defaults('yhoo-1996-2014.txt', '2005-01-01', '2006-12-31',
                      cash=50000.0,
                      params=dict(myname='St1', dtarget='MyData0')),
    options=dict(both=True, copydata=False),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='MyData0')
    dtarget = 'MyData0'
    if o.copydata:
        cerebro.adddata(data.copyas('MyData1'))
        dtarget = 'MyData1'
    if o.both:
        cerebro.addstrategy(TheStrategy2, myname='St2', dtarget=dtarget)
''')

for name, d0, d1, dates in (
        ('multidata-strategy/multidata-strategy.py', 'orcl-1995-2014.txt',
         'yhoo-1996-2014.txt', ('2003-01-01', '2005-12-31')),
        ('multidata-strategy/multidata-strategy-unaligned.py',
         'orcl-2003-2005.txt', 'yhoo-2003-2005.txt',
         ('2003-01-01', '2005-12-31'))):
    SPECS[name] = dict(
        doc='''Two datas: signals come from an SMA crossover on data1 and
the orders are placed on data0 (and data1). data0 is the selected feed,
data1 is the file in the "data1" option.''' + (
            '' if 'unaligned' not in name else '''

The "unaligned" variant only trades data0, with datas that do not share all
trading days.'''),
        defaults=defaults(d0, *dates, cash=100000.0, commission=0.5),
        options=dict(data1=d1, runnext=False, nopreload=False,
                     oldsync=False),
        configure='''    o = ctx.opts
    cerebro.adddata(data)
    cerebro.adddata(ctx.load(o.data1))
    cerebro.p.runonce = not o.runnext
    cerebro.p.preload = not o.nopreload
    cerebro.p.oldsync = o.oldsync
''')

SPECS['multi-example/mult-values.py'] = dict(
    doc='''Trading three datas at once with brackets (or plain buys) entered
on specific weekdays and closed after a holding period, sized by a custom
sizer that logs its decisions. d0 is the selected feed; d1 and d2 come from
the options.''',
    defaults=defaults('nvda-1999-2014.txt', '2001-01-01', '2007-01-01',
                      commission=0.1),
    options=dict(data1='yhoo-1996-2014.txt', data2='orcl-1995-2014.txt',
                 stake=1),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='d0')
    data1 = ctx.load(o.data1)
    data1.plotinfo.plotmaster = data
    cerebro.adddata(data1, name='d1')
    data2 = ctx.load(o.data2)
    data2.plotinfo.plotmaster = data
    cerebro.adddata(data2, name='d2')
    cerebro.addsizer(TestSizer, stake=o.stake)
''')

SPECS['multitrades/multitrades.py'] = dict(
    doc='''Several trades open at once on one data by giving orders a
tradeid (`mtrade`). The MTradeObserver (mtradeobserver.py) plots the P&L of
each trade id.''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31',
                      cash=100000.0),
    options=dict(comm=2.0, mult=10, margin=2000.0),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    cerebro.broker.setcommission(commission=o.comm, mult=o.mult,
                                 margin=o.margin)
    cerebro.addobserver(mtradeobserver.MTradeObserver)
''')

SPECS['observer-benchmark/observer-benchmark.py'] = dict(
    doc='''Benchmark and TimeReturn observers: compare the strategy returns
with the returns of a data (the traded one, or another file with
benchdata1) over a timeframe.''',
    replace=[("print('CLOSE {} @%{}'.format(size,",
              "print('CLOSE {} @%{}'.format(self.position.size,")],
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31',
                      cash=50000.0, params=dict(period=30)),
    options=dict(timereturn=False, timeframe='', benchdata1=False,
                 data1='orcl-1995-2014.txt'),
    choices=dict(timeframe=['', 'days', 'weeks', 'months', 'years',
                            'notimeframe']),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    tframe = TIMEFRAMES[o.timeframe or None]
    if o.timereturn:
        cerebro.addobserver(bt.observers.TimeReturn, timeframe=tframe)
    else:
        benchdata = data
        if o.benchdata1:
            data1 = ctx.load(o.data1)
            cerebro.adddata(data1, name='Data1')
            benchdata = data1
        cerebro.addobserver(bt.observers.Benchmark, data=benchdata,
                            timeframe=tframe)
''')

SPECS['observers/observers-default-drawdown.py'] = dict(
    doc='''The DrawDown observer (and the old implementation) used from
within the strategy through self.stats to log the drawdown on every bar.''',
    defaults=defaults('2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.addobserver(bt.observers.DrawDown)
    cerebro.addobserver(bt.observers.DrawDown_Old)
''')

SPECS['observers/observers-default.py'] = dict(
    doc='''The default observers (stdstats=True): Broker (cash/value),
BuySell and Trades. In Backtrader Studio they correspond to the equity
chart, the buy/sell markers and the Trades table.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample only shows the default observers\'\'\'
''',
    defaults=defaults('2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Trades)
''')

SPECS['observers/observers-orderobserver.py'] = dict(
    doc='''A custom observer (orderobserver.py) that marks where buy limit
orders were created and where they expired.''',
    defaults=defaults('2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.addobserver(OrderObserver)
''')

SPECS['oandatest/oandatest.py'] = dict(
    doc='''Oanda test strategy: logs every bar and, with `trade`, buys or
sells with the configured order type (or a bracket) and counters half of the
position.''' + LIVE_NOTE,
    drop=['StoreCls', 'DataCls'],
    replace=[('''        usebracket=False,
    )
''', '''        usebracket=False,
        backtest=True,  # Backtrader Studio: act as if data were live
    )
'''), ('''    def start(self):
        if self.data0.contractdetails is not None:''', '''    def start(self):
        if self.p.backtest:
            self.datastatus = 1
        if getattr(self.data0, 'contractdetails', None) is not None:''')],
    defaults=defaults('orcl-2014.txt', cash=100000.0,
                      params=dict(trade=True)),
)

SPECS['oco/oco.py'] = dict(
    doc='''One-Cancels-Others: three buy limit orders at different prices
where the execution (or cancellation) of one cancels the others.''',
    defaults=defaults('2005-2006-day-001.txt'),
)

SPECS['optimization/optimization.py'] = dict(
    doc='''Strategy from the optimization sample (an SMA and a MACD, no
trading). The sample runs cerebro.optstrategy over ranges of the four
periods; Backtrader Studio runs one combination at a time: set the periods
in the params.''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31'),
)

for name, feed in (('order-close/close-daily.py', '2005-2006-day-001.txt'),
                   ('order-close/close-minute.py', '2006-min-005.txt')):
    daily = 'daily' in name
    SPECS[name] = dict(
        doc='''Order.Close execution: orders are matched with the closing
price of the session. With `eosbar` the broker treats a bar at the session
end time as the close of the session. ''' + (
            'Random entries: every run differs.' if daily else
            'Enters and exits every two days on intraday data.'),
        replace=([('dtime = datetime.combine(data.datetime.date(), '
                   'self.p.endtime)',
                   'dtime = datetime.datetime.combine(data.datetime.date(),'
                   ' self.p.endtime)')] if daily else []),
        defaults=defaults(feed),
        options=dict(eosbar=False, tend='', **(dict(filltime='') if daily
                                               else {})),
        configure='''    o = ctx.opts
    if o.tend:
        data = ctx.make_data(
            sessionend=datetime.datetime.strptime(o.tend, '%H:%M'))
''' + ('''    if o.filltime:
        filltime = datetime.datetime.strptime(o.filltime, '%H:%M:%S').time()
        data.addfilter(SessionEndFiller, endtime=filltime)
''' if daily else '') + '''    cerebro.adddata(data)
    if o.eosbar:
        cerebro.broker.seteosbar(True)
''')

SPECS['order-execution/order-execution.py'] = dict(
    doc='''Order execution types: buy with a Market, Close, Limit, Stop or
StopLimit order (param exectype) when the close crosses an SMA; perc1/perc2
set the limit/stop distance and `valid` the order validity in days.''',
    defaults=defaults('2006-day-001.txt',
                      params=dict(perc1=0, perc2=0, valid=0)),
    choices=dict(exectype=['Market', 'Close', 'Limit', 'Stop', 'StopLimit']),
)

SPECS['order-history/order-history.py'] = dict(
    doc='''Order history: feed a list of past executions (ORDER_HISTORY) to
cerebro and let backtrader compute the analyzers for them. Pick the St class
and enable the "order_history" option to replay it; SmaCross is the
strategy that generated those orders.''',
    defaults=defaults('2005-2006-day-001.txt'),
    options=dict(order_history=False),
    configure='''    cerebro.adddata(data)
    if ctx.opts.order_history:
        cerebro.add_order_history(ORDER_HISTORY, notify=True)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Months)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer)
''')

SPECS['order_target/order_target.py'] = dict(
    doc='''order_target_size / order_target_value / order_target_percent:
every bar the target changes with the day of the month and the strategy
lets backtrader work out the order needed to reach it. Enable one of the
three use_target_* params.''',
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31',
                      cash=1000000.0, params=dict(use_target_size=True)),
)

SPECS['partial-plot/partial-plot.py'] = dict(
    doc='''Indicators on a daily data plus a weekly resampled copy (the
sample shows plotting only part of a run).''',
    defaults=defaults('2005-2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks)
''')

SPECS['pinkfish-challenge/pinkfish-challenge.py'] = dict(
    doc='''The "pinkfish challenge": buy at the close of the day that makes a
new 20-day high and sell after `sellafter` days. Each daily bar is split
into an open-high-low step and a close step (replayed from a "minutes"
feed) so the decision can be taken and executed on the same close.''',
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31',
                      cash=50000.0),
    options=dict(no_replay=False, oldbuysell=False),
    configure='''    o = ctx.opts
    cerebro.broker.set_eosbar(True)
    if o.no_replay:
        data = ctx.make_data(timeframe=bt.TimeFrame.Days, compression=1)
        data.addfilter(DayStepsCloseFilter)
        cerebro.adddata(data)
    else:
        data = ctx.make_data(timeframe=bt.TimeFrame.Minutes, compression=1)
        data.addfilter(DayStepsReplayFilter)
        cerebro.replaydata(data, timeframe=bt.TimeFrame.Days, compression=1)
    cerebro.p.runonce = False
    cerebro.p.preload = False
    cerebro.p.oldbuysell = o.oldbuysell
''')

SPECS['pivot-point/ppsample.py'] = dict(
    doc='''Pivot points calculated on monthly bars (resampled from the daily
feed) and used on the daily timeframe. pivotpoint.py holds two stand-alone
implementations of the indicator.''',
    defaults=defaults('2005-2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Months)
    cerebro.p.runonce = False
''')

SPECS['plot-same-axis/plot-same-axis.py'] = dict(
    doc='''Indicators created for plotting: SMA, MACD, Stochastic and RSI,
with params to plot some of them on the same axis as others (matplotlib
plotting options; Backtrader Studio shows each in its own panel).''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31'),
)

SPECS['psar/psar.py'] = dict(
    doc='''Parabolic SAR on daily data.''',
    defaults=defaults('2005-2006-day-001.txt'),
)

SPECS['psar/psar-intraday.py'] = dict(
    doc='''Parabolic SAR on 5-minute data and on the same data resampled to
15 minutes.''',
    defaults=defaults('2006-min-005.txt'),
    configure='''    data = ctx.make_data(timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)
''')

SPECS['pyfolio2/pyfoliotest.py'] = dict(
    replace=[('''        super(self.__class__, self).next()
''', '''        # Backtrader Studio: SignalStrategy already runs the signals before
        # next(); calling super().next() here recursed forever
''')],
    doc='''SMA crossover signal strategy with TimeReturn, SharpeRatio and SQN
analyzers and the PyFolio analyzer (returns, positions, transactions and
gross leverage ready for pyfolio). The sample loaded VisualChart data and
drew a pyfolio tear sheet; here it uses the selected feed and the PyFolio
output is in the Analyzers tab (pyfolio itself is not installed).''',
    defaults=defaults('nvda-1999-2014.txt', '2013-01-01', '2014-12-31',
                      cash=50000.0, stake=10),
    options=dict(pyfolio=True, pftimeframe='days'),
    choices=dict(pftimeframe=list(('minutes', 'days', 'weeks', 'months',
                                   'years'))),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.SQN)
    if o.pyfolio:
        cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio',
                            timeframe=_TFRAMES[o.pftimeframe])
''')

SPECS['pyfoliotest/pyfoliotest.py'] = dict(
    doc='''Random trading on three datas with the PyFolio analyzer collecting
returns, positions and transactions (shown in the Analyzers tab; pyfolio
itself is not installed, so no tear sheet). Random entries: every run
differs.''',
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31',
                      cash=50000.0),
    options=dict(data1='orcl-1995-2014.txt', data2='nvda-1999-2014.txt',
                 pyfolio=True),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    cerebro.adddata(ctx.load(o.data1), name='Data1')
    cerebro.adddata(ctx.load(o.data2), name='Data2')
    if o.pyfolio:
        cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')
''')

SPECS['relative-volume/relative-volume.py'] = dict(
    doc='''RelativeVolumeByBar (relvolbybar.py): the volume of each intraday
bar relative to the same bar of the previous session.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample is about the indicator\'\'\'
''',
    defaults=defaults('2006-01-02-volume-min-001.txt', '2006-01-01',
                      '2006-12-31'),
    options=dict(prestart='08:00', start='09:15', end='17:15', writer=False,
                 wrcsv=False),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    totime = lambda s: datetime.datetime.strptime(s, '%H:%M').time()
    cerebro.addindicator(RelativeVolumeByBar, prestart=totime(o.prestart),
                         start=totime(o.start), end=totime(o.end))
''' + WRITER)

SPECS['renko/renko.py'] = dict(
    doc='''Renko bricks made with the Renko filter, either replacing the data
or (dual) as a second data next to it, with an RSI on each. renko takes the
filter kwargs, e.g. size=5 or autosize=10.''',
    defaults=defaults('2005-2006-day-001.txt'),
    options=dict(renko='', dual=False),
    configure='''    o = ctx.opts
    fkwargs = eval('dict(' + o.renko + ')')
    if not o.dual:
        data.addfilter(bt.filters.Renko, **fkwargs)
        cerebro.adddata(data)
    else:
        cerebro.adddata(data)
        data1 = data.clone()
        data1.addfilter(bt.filters.Renko, **fkwargs)
        cerebro.adddata(data1)
''')

SPECS['resample-tickdata/resample-tickdata.py'] = dict(
    doc='''Resampling tick data to larger timeframes (ticks, seconds,
minutes, ...). Reads the selected file as tick data (ticksample.csv by
default); bar2edge/adjbartime/rightedge control how bars are aligned.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy: the sample is about resampling ticks\'\'\'
''',
    defaults=defaults('ticksample.csv'),
    options=dict(timeframe='ticks', compression=1, nobar2edge=False,
                 noadjbartime=False, rightedge=False, writer=False,
                 wrcsv=False),
    choices=dict(timeframe=['ticks', 'microseconds', 'seconds', 'minutes',
                            'daily', 'weekly', 'monthly']),
    configure='''    o = ctx.opts
    datapath = (ctx.feed['path'] if ctx.feed['type'] == 'file'
                else ctx.datapath('ticksample.csv'))
    ticks = btfeeds.GenericCSVData(dataname=datapath,
                                   dtformat='%Y-%m-%dT%H:%M:%S.%f',
                                   timeframe=bt.TimeFrame.Ticks)
    tframes = dict(ticks=bt.TimeFrame.Ticks,
                   microseconds=bt.TimeFrame.MicroSeconds,
                   seconds=bt.TimeFrame.Seconds,
                   minutes=bt.TimeFrame.Minutes,
                   daily=bt.TimeFrame.Days,
                   weekly=bt.TimeFrame.Weeks,
                   monthly=bt.TimeFrame.Months)
    cerebro.resampledata(ticks, timeframe=tframes[o.timeframe],
                         compression=o.compression,
                         bar2edge=not o.nobar2edge,
                         adjbartime=not o.noadjbartime,
                         rightedge=o.rightedge)
''' + WRITER)

SPECS['rollover/rollover.py'] = dict(
    doc='''Chaining or rolling over futures contracts into one continuous
data. The sample used VisualChart FESX contracts; here the files in the
"files" option (from backtrader/datas) are chained, or rolled over with the
"rollover" option. checkdate/checkvolume only make sense with futures names
like 199FESXM4.''',
    defaults=defaults('orcl-2003-2005.txt'),
    options=dict(files='orcl-2003-2005.txt,orcl-2014.txt', rollover=False,
                 checkdate=False, checkcondition=False),
    configure='''    o = ctx.opts
    # pandas=True: plain OHLCV-OI feeds (Yahoo CSVs carry an extra line)
    ffeeds = [ctx.load(x.strip(), pandas=True)
              for x in o.files.split(',') if x.strip()]
    rollkwargs = dict()
    if o.checkdate:
        rollkwargs['checkdate'] = checkdate
        if o.checkcondition:
            rollkwargs['checkcondition'] = checkvolume
    if o.rollover:
        cerebro.rolloverdata(name='FESX', *ffeeds, **rollkwargs)
    else:
        cerebro.chaindata(name='FESX', *ffeeds)
''')

SPECS['sharpe-timereturn/sharpe-timereturn.py'] = dict(
    doc='''TimeReturn and SharpeRatio analyzers over a timeframe (with
riskfreerate, annualize, factor ... from the options) on the built-in
SMA_CrossOver strategy. A WriterFile summary is printed in the Log tab.''',
    extra='''class SmaCrossOver(bt.strategies.MA_CrossOver):
    \'\'\'backtrader's built-in SMA_CrossOver (MA_CrossOver) strategy, which
    the sample adds with cerebro.addstrategy(bt.strategies.SMA_CrossOver)\'\'\'
''',
    defaults=defaults('2005-2006-day-001.txt', '2005-01-01', '2006-12-31'),
    options=dict(tframe='years', annualize=False, riskfreerate=None,
                 factor=None, stddev_sample=False, no_convertrate=False,
                 writercsv=False),
    choices=dict(tframe=['days', 'weeks', 'months', 'years']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    tframes = dict(days=bt.TimeFrame.Days, weeks=bt.TimeFrame.Weeks,
                   months=bt.TimeFrame.Months, years=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=tframes[o.tframe])
    shkwargs = dict()
    if o.annualize:
        shkwargs['annualize'] = True
    if o.riskfreerate is not None:
        shkwargs['riskfreerate'] = float(o.riskfreerate)
    if o.factor is not None:
        shkwargs['factor'] = float(o.factor)
    if o.stddev_sample:
        shkwargs['stddev_sample'] = True
    if o.no_convertrate:
        shkwargs['convertrate'] = False
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                        timeframe=tframes[o.tframe], **shkwargs)
    cerebro.addwriter(bt.WriterFile, csv=o.writercsv, rounding=4)
''')

SPECS['signals-strategy/signals-strategy.py'] = dict(
    doc='''Signals: the close minus its SMA as the main signal (long/short,
long only or short only) plus an optional exit signal made from two SMAs.
The sample fed them to cerebro.add_signal(); here SignalsStrategy adds them
from its params.''',
    extra='''class SignalsStrategy(bt.SignalStrategy):
    \'\'\'SignalStrategy fed with the sample's signals (what cerebro builds
    for cerebro.add_signal)\'\'\'
    params = dict(signal='longshort', smaperiod=30, exitsignal='',
                  exitperiod=5)

    def __init__(self):
        self.signal_add(MAINSIGNALS[self.p.signal],
                        SMACloseSignal(period=self.p.smaperiod))
        if self.p.exitsignal:
            self.signal_add(EXITSIGNALS[self.p.exitsignal],
                            SMAExitSignal(p1=self.p.exitperiod,
                                          p2=self.p.smaperiod))
''',
    defaults=defaults('2005-2006-day-001.txt', cash=50000.0),
    choices=dict(signal=['longshort', 'longonly', 'shortonly'],
                 exitsignal=['', 'longexit', 'shortexit']),
)

SPECS['sigsmacross/sigsmacross.py'] = dict(
    doc='''The README's SMA crossover as a SignalStrategy, logging executions
and trade profits. The sample downloaded YHOO from Yahoo, which is no longer
listed: the offline yhoo file is used instead.''',
    defaults=defaults('yhoo-1996-2014.txt', '2011-01-01', '2012-12-31'),
)

SPECS['sigsmacross/sigsmacross2.py'] = dict(
    doc='''The minimal SMA crossover signal strategy from the README (the
sample script ran it at import time). YHOO is no longer on Yahoo: the
offline yhoo file is used instead.''',
    drop_module_code=True,
    defaults=defaults('yhoo-1996-2014.txt', '2011-01-01', '2012-12-31'),
)

SPECS['sizertest/sizertest.py'] = dict(
    doc='''Custom sizers: LongOnly (never sells more than is held) or
backtrader's FixedReverser (doubles the stake to reverse a position), used
by an SMA crossover that always buys/sells on the cross.''',
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31',
                      cash=50000.0),
    options=dict(longonly=False, stake=1),
    configure='''    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    if o.longonly:
        cerebro.addsizer(LongOnly, stake=o.stake)
    else:
        cerebro.addsizer(bt.sizers.FixedReverser, stake=o.stake)
''')

SPECS['slippage/slippage.py'] = dict(
    doc='''Slippage: percentage (slip_perc) or fixed (slip_fixed) slippage
applied by the broker, with slip_open / slip_match / slip_out controlling
the details, on an SMA crossover signal strategy. Compare the prices in the
Log tab.''',
    replace=[('''class SlipSt(bt.SignalStrategy):
    opcounter = itertools.count(1)
''', '''class SlipSt(bt.SignalStrategy):
    # Backtrader Studio: the signal was added with cerebro.add_signal in the
    # sample; it is created here from the params instead
    params = dict(period1=10, period2=30, longonly=False)

    opcounter = itertools.count(1)

    def __init__(self):
        stype = (bt.signal.SIGNAL_LONG if self.p.longonly
                 else bt.signal.SIGNAL_LONGSHORT)
        self.signal_add(stype, SMACrossOver(p1=self.p.period1,
                                            p2=self.p.period2))
''')],
    defaults=defaults('2005-2006-day-001.txt', cash=50000.0),
    options=dict(slip_perc=None, slip_fixed=None, no_slip_match=False,
                 slip_out=False, slip_open=False),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    kwargs = dict(slip_open=o.slip_open, slip_match=not o.no_slip_match,
                  slip_out=o.slip_out)
    if o.slip_perc is not None:
        cerebro.broker.set_slippage_perc(float(o.slip_perc), **kwargs)
    elif o.slip_fixed is not None:
        cerebro.broker.set_slippage_fixed(float(o.slip_fixed), **kwargs)
''')

SPECS['sratio/sratio.py'] = dict(
    doc='''How the Sharpe Ratio is calculated, step by step, for two annual
returns and a risk-free rate. The sample is plain Python; here the
calculation runs in the strategy's start() and prints to the Log tab.''',
    extra='''import backtrader as bt


class SharpeRatioSteps(bt.Strategy):
    \'\'\'Prints the Sharpe Ratio calculation of the sample (no trading)\'\'\'
    params = dict(ret1=0.023286, ret2=0.0257816485323, riskfreerate=0.01)

    def start(self):
        returns = [self.p.ret1, self.p.ret2]
        retfree = self.p.riskfreerate
        print('returns is:', returns, ' - retfree is:', retfree)

        # Directly from backtrader
        retfree = itertools.repeat(retfree)
        ret_free = map(operator.sub, returns, retfree)  # excess returns
        ret_free_avg = average(list(ret_free))  # mean of the excess returns
        print('returns excess mean:', ret_free_avg)

        retdev = standarddev(returns)  # standard deviation
        print('returns standard deviation:', retdev)

        ratio = ret_free_avg / retdev  # mean excess returns  / std deviation
        print('Sharpe Ratio is:', ratio)
''',
    defaults=defaults('2006-day-001.txt'),
)

SPECS['stop-trading/stop-loss-approaches.py'] = dict(
    doc='''Three ways of protecting an EMA-crossover entry with a stop loss
or trailing stop: manual (stop sent after the buy executes), manualcheat
(both sent together using cheat-on-close) and auto (stop as child of the
buy). BaseStrategy only holds the signal. Set `trail` to a trail amount to
use StopTrail orders.''',
    defaults=defaults('2005-2006-day-001.txt',
                      strategy='ManualStopOrStopTrail'),
)

SPECS['stoptrail/trail.py'] = dict(
    doc='''StopTrail / StopTrailLimit orders: after an MA crossover entry a
trailing stop follows the price by trailamount or trailpercent. The form
uses trailpercent=0.02 (the sample expected it from the command line).''',
    defaults=defaults('2005-2006-day-001.txt',
                      params=dict(trailpercent=0.02)),
)

SPECS['strategy-selection/strategy-selection.py'] = dict(
    doc='''Strategy selection: the sample optimized over an index to run St0
(SMA 10/30 crossover) and St1 (close/SMA 10 crossover) and compare their
Returns. Pick one class at a time in the form.''',
    defaults=defaults('2005-2006-day-001.txt'),
    configure='''    cerebro.adddata(data)
    cerebro.addanalyzer(bt.analyzers.Returns)
''')

TALIB_CHECK = '''    if not hasattr(bt.talib, 'SMA'):
        raise ImportError('TA-Lib is not installed in the backtrader env: '
                          'pip install TA-Lib (needs the TA-Lib C library)')
'''

TALIB_NOTE = '''

Needs the TA-Lib Python package (not installed in the backtrader env:
`pip install TA-Lib`, which needs the TA-Lib C library).'''

SPECS['talib/tablibsartest.py'] = dict(
    doc='''TA-Lib's SAR next to backtrader's own ParabolicSAR.''' + TALIB_NOTE,
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31'),
    options=dict(use_next=False),
    configure=TALIB_CHECK + '''    cerebro.adddata(data)
    cerebro.p.runonce = not ctx.opts.use_next
''')

SPECS['talib/talibtest.py'] = dict(
    doc='''TA-Lib indicators side by side with backtrader's equivalents (pick
one with `ind`), plus the CDLDOJI candle pattern.''' + TALIB_NOTE,
    defaults=defaults('yhoo-1996-2015.txt', '2005-01-01', '2006-12-31'),
    options=dict(use_next=False),
    choices=dict(ind=['sma', 'ema', 'stoc', 'rsi', 'macd', 'bollinger',
                      'aroon', 'ultimate', 'trix', 'kama', 'adxr', 'dema',
                      'ppo', 'tema', 'roc', 'williamsr']),
    configure=TALIB_CHECK + '''    cerebro.adddata(data)
    cerebro.p.runonce = not ctx.opts.use_next
''')

for name, feed, tf in (('timers/scheduled.py', '2005-2006-day-001.txt',
                        'bt.TimeFrame.Days, compression=1'),
                       ('timers/scheduled-min.py', '2006-min-005.txt',
                        'bt.TimeFrame.Minutes, compression=5')):
    SPECS[name] = dict(
        doc='''Timers: add_timer() calls notify_timer at the session start (or
end, or a given time), optionally with an offset, repeat, weekdays%s.
With `cheat` a second timer fires before the bar is processed and buys.
when: 0 = SESSION_TIME, 1 = SESSION_START, 2 = SESSION_END or a
datetime.time(...).''' % (' and monthdays' if 'min' in name else ''),
        defaults=defaults(feed),
        configure='''    data = ctx.make_data(timeframe=%s,
                         sessionstart=datetime.time(9, 0),
                         sessionend=datetime.time(17, 30))
    cerebro.adddata(data)
''' % tf)

SPECS['tradingcalendar/tcal.py'] = dict(
    doc='''Trading calendars: a daily data resampled to weeks/months/years
with a calendar telling backtrader which days are trading days, so the
resampled bar can be delivered at the right moment. owncal uses the NYSE
2016 holidays defined here; pandascal needs pandas_market_calendars. The
sample downloaded YHOO for 2016 (no longer listed): SPY is used instead.''',
    defaults=defaults('yahoo:SPY', '2016-01-01', '2016-12-31'),
    options=dict(timeframe='Weeks', owncal=False, pandascal=''),
    choices=dict(timeframe=['Weeks', 'Months', 'Years']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    d1 = cerebro.resampledata(data,
                              timeframe=getattr(bt.TimeFrame, o.timeframe))
    d1.plotinfo.plotmaster = data
    d1.plotinfo.sameaxis = True
    if o.pandascal:
        cerebro.addcalendar(o.pandascal)
    elif o.owncal:
        cerebro.addcalendar(NYSE_2016)
''')

SPECS['tradingcalendar/tcal-intra.py'] = dict(
    doc='''Trading calendar with intraday data resampled to days, including
early closing days and timezones (tzinput/tz need pytz). The sample used a
2016 intraday file that is not in backtrader/datas; the 5-minute sample
data is used by default (the NYSE_2016 calendar does not cover 2006).''',
    defaults=defaults('2006-min-005.txt'),
    options=dict(tzinput='', tz='', owncal=False, pandascal=''),
    configure='''    o = ctx.opts
    kwargs = dict()
    if o.tzinput:
        kwargs['tzinput'] = o.tzinput
    if o.tz:
        kwargs['tz'] = o.tz
    if kwargs:
        data = ctx.make_data(**kwargs)
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Days)
    if o.pandascal:
        cerebro.addcalendar(o.pandascal)
    elif o.owncal:
        cerebro.addcalendar(NYSE_2016())
''')

SPECS['vctest/vctest.py'] = dict(
    doc='''VisualChart test strategy: logs every bar and, with `trade`, buys
with the configured order type and sells half of the position.''' + LIVE_NOTE,
    replace=[('''        pstoplimit=None,
    )
''', '''        pstoplimit=None,
        backtest=True,  # Backtrader Studio: act as if data were live
    )
'''), ('''    def start(self):
        header = ''', '''    def start(self):
        if self.p.backtest:
            self.datastatus = 1
        header = ''')],
    defaults=defaults('orcl-2014.txt', cash=100000.0,
                      params=dict(trade=True)),
)

SPECS['volumefilling/volumefilling.py'] = dict(
    doc='''Volume filling: orders sized at a percentage of the bar volume are
filled completely, or partially by a filler (FixedSize, FixedBarPerc,
BarPointPerc; filler_args e.g. perc=50). Watch the partial executions in the
Log and Orders tabs.''',
    defaults=defaults('2006-volume-day-001.txt', cash=500e6),
    options=dict(filler='', filler_args=''),
    choices=dict(filler=['', 'FixedSize', 'FixedBarPerc', 'BarPointPerc']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    if o.filler:
        fillerkwargs = eval('dict(' + o.filler_args + ')')
        cerebro.broker.set_filler(FILLERS[o.filler](**fillerkwargs))
''')

SPECS['vwr/vwr.py'] = dict(
    doc='''Variability-Weighted Return (VWR) next to Returns, SQN,
SharpeRatio_A and monthly/yearly TimeReturn, on the built-in SMA_CrossOver
strategy (see the Analyzers tab and the WriterFile summary in Log).''',
    extra='''class SmaCrossOver(bt.strategies.MA_CrossOver):
    \'\'\'backtrader's built-in SMA_CrossOver (MA_CrossOver) strategy, which
    the sample adds with cerebro.addstrategy(bt.strategies.SMA_CrossOver)\'\'\'
''',
    defaults=defaults('2005-2006-day-001.txt'),
    options=dict(tframe='', tann=None, sigma_max=None, tau=None,
                 writercsv=False),
    choices=dict(tframe=['', 'days', 'weeks', 'months', 'years']),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    lrkwargs = dict()
    if o.tframe:
        lrkwargs['timeframe'] = TFRAMES[o.tframe]
    if o.tann is not None:
        lrkwargs['tann'] = float(o.tann)
    cerebro.addanalyzer(bt.analyzers.Returns, **lrkwargs)
    vwrkwargs = dict(lrkwargs)
    if o.sigma_max is not None:
        vwrkwargs['sigma_max'] = float(o.sigma_max)
    if o.tau is not None:
        vwrkwargs['tau'] = float(o.tau)
    cerebro.addanalyzer(bt.analyzers.SQN)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio_A)
    cerebro.addanalyzer(bt.analyzers.VWR, **vwrkwargs)
    cerebro.addanalyzer(bt.analyzers.TimeReturn,
                        timeframe=bt.TimeFrame.Months)
    cerebro.addanalyzer(bt.analyzers.TimeReturn,
                        timeframe=bt.TimeFrame.Years)
    cerebro.addwriter(bt.WriterFile, csv=o.writercsv, rounding=4)
''')

SPECS['weekdays-filler/weekdaysaligner.py'] = dict(
    doc='''Aligning two datas with different trading days: WeekDaysFiller
(weekdaysfiller.py) adds the missing weekdays (NaN bars, or the last close
with fillclose). data0 is the selected feed; data1 is the file in the
"data1" option or a clone of data0.''',
    defaults=defaults('yhoo-1996-2014.txt', '2012-01-01', '2012-12-31'),
    options=dict(data1='orcl-1995-2014.txt', fillclose=False, filler=False,
                 filler0=False, filler1=False),
    configure='''    o = ctx.opts
    data1 = ctx.load(o.data1) if o.data1 else data.clone()
    if o.filler or o.filler0:
        data.addfilter(WeekDaysFiller, fillclose=o.fillclose)
    if o.filler or o.filler1:
        data1.addfilter(WeekDaysFiller, fillclose=o.fillclose)
    cerebro.adddata(data)
    cerebro.adddata(data1)
''')

SPECS['writer-test/writer-test.py'] = dict(
    doc='''WriterFile output: every bar of the data, the strategy lines and
indicators (csv=True) plus a final summary of the analyzers, in the Log tab.
The strategy is an SMA crossover trading a futures-like asset.''',
    defaults=defaults('2006-day-001.txt', '2006-01-01', '2006-12-31',
                      cash=100000.0),
    options=dict(comm=2.0, mult=10, margin=2000.0, writercsv=False),
    configure='''    o = ctx.opts
    cerebro.adddata(data)
    cerebro.broker.setcommission(commission=o.comm, mult=o.mult,
                                 margin=o.margin)
    cerebro.addanalyzer(SQN)
    cerebro.addwriter(bt.WriterFile, csv=o.writercsv, rounding=2)
''')

SPECS['yahoo-test/yahoo-test.py'] = dict(
    doc='''Downloading data from Yahoo Finance (with an SMA on top). YHOO is
no longer listed, so AAPL is the default ticker.''',
    extra='''class St(bt.Strategy):
    \'\'\'Empty strategy with the SMA the sample adds via cerebro\'\'\'
    params = dict(period=15)

    def __init__(self):
        btind.SMA(period=self.p.period)
''',
    defaults=defaults('yahoo:AAPL', '2006-01-01', '2006-12-31'),
    options=dict(writer=False, wrcsv=False),
    configure='''    cerebro.adddata(data)
''' + WRITER)

# helper modules imported by other samples: copied verbatim + note
HELPERS = {
    'data-filler/relativevolume.py': 'RelativeVolume indicator used by '
    'data-filler.py (helper module, no strategy).',
    'multitrades/mtradeobserver.py': 'MTradeObserver used by multitrades.py '
    '(helper module, no strategy).',
    'observers/orderobserver.py': 'OrderObserver used by '
    'observers-orderobserver.py (helper module, no strategy).',
    'pivot-point/pivotpoint.py': 'Stand-alone PivotPoint indicators (helper '
    'module, no strategy).',
    'relative-volume/relvolbybar.py': 'RelativeVolumeByBar indicator used by '
    'relative-volume.py (helper module, no strategy).',
    'weekdays-filler/weekdaysfiller.py': 'WeekDaysFiller filter used by '
    'weekdaysaligner.py (helper module, no strategy).',
}

SETUP_HEADER = '''

# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
'''


def is_main_guard(node):
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == '__name__')


def strip_source(src, spec):
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    drop = DROP_FUNCS | set(spec.get('drop', []))
    kill = set()
    for node in tree.body:
        remove = False
        if isinstance(node, ast.FunctionDef) and node.name in drop:
            remove = True
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in drop
                for t in node.targets):
            remove = True
        elif is_main_guard(node):
            remove = True
        elif isinstance(node, ast.Import) and \
                [a.name for a in node.names] == ['argparse']:
            remove = True
        elif spec.get('drop_module_code') and not isinstance(
                node, (ast.Import, ast.ImportFrom, ast.ClassDef,
                       ast.FunctionDef)):
            remove = True
        if remove:
            start = node.lineno - 1
            if getattr(node, 'decorator_list', None):
                start = node.decorator_list[0].lineno - 1
            kill.update(range(start, node.end_lineno))
    out = ''.join(l for i, l in enumerate(lines) if i not in kill)
    return re.sub(r'\n{4,}', '\n\n\n', out).rstrip() + '\n'


def add_docstring(src, doc):
    '''Insert the module docstring after the license comment header'''
    lines = src.splitlines(keepends=True)
    i = 0
    while i < len(lines) and (lines[i].startswith('#') or
                              not lines[i].strip()):
        i += 1
    # keep the shebang/coding/license block, then the docstring
    return ''.join(lines[:i]) + "'''" + doc + "\n'''\n" + ''.join(lines[i:])


def build(rel, spec):
    src = open(os.path.join(SAMPLES, rel)).read()
    body = strip_source(src, spec)
    for old, new in spec.get('replace', []):
        if old not in body:
            raise SystemExit('%s: replacement not found:\n%s' % (rel, old))
        body = body.replace(old, new)
    doc = spec['doc'] + '\n\nPorted from backtrader/samples/%s.' % rel
    body = add_docstring(body, doc)
    if spec.get('extra'):
        body = body.rstrip() + '\n\n\n' + spec['extra'].rstrip() + '\n'
    setup = SETUP_HEADER
    setup += dict_lit('DEFAULTS', spec['defaults'])
    if spec.get('options'):
        setup += '\n' + dict_lit('OPTIONS', spec['options'])
    if spec.get('choices'):
        setup += '\n' + dict_lit('CHOICES', spec['choices'])
    if spec.get('configure'):
        setup += ('\n\ndef configure(cerebro, data, ctx):\n'
                  '    \'\'\'Set up cerebro like the sample\'s runstrat()\'\'\'\n'
                  + spec['configure'])
    return body.rstrip() + '\n' + setup


def main():
    samples = sorted(os.path.relpath(os.path.join(d, f), SAMPLES)
                     for d, _, fs in os.walk(SAMPLES) for f in fs
                     if f.endswith('.py'))
    missing = [s for s in samples if s not in SPECS and s not in HELPERS]
    extra = [s for s in SPECS if s not in samples]
    if missing or extra:
        raise SystemExit('missing specs: %s / unknown: %s' % (missing, extra))
    for rel in samples:
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in HELPERS:
            src = open(os.path.join(SAMPLES, rel)).read()
            out = add_docstring(src, HELPERS[rel] + '\n\nCopied from '
                                'backtrader/samples/%s.' % rel)
        else:
            out = build(rel, SPECS[rel])
        compile(out, dst, 'exec')
        with open(dst, 'w') as f:
            f.write(out)
    print('ported %d files' % len(samples))


if __name__ == '__main__':
    main()
