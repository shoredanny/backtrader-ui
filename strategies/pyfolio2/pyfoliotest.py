#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2023 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
'''SMA crossover signal strategy with TimeReturn, SharpeRatio and SQN
analyzers and the PyFolio analyzer (returns, positions, transactions and
gross leverage ready for pyfolio). The sample loaded VisualChart data and
drew a pyfolio tear sheet; here it uses the selected feed and the PyFolio
output is in the Analyzers tab (pyfolio itself is not installed).

Ported from backtrader/samples/pyfolio2/pyfoliotest.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import collections
import datetime


import backtrader as bt


class St(bt.SignalStrategy):
    params = (
        ('pfast', 13),
        ('pslow', 50),
        ('printdata', False),
        ('stake', 1000),
        ('short', False),
    )

    def __init__(self):
        self.sfast = bt.indicators.SMA(period=self.p.pfast)
        self.sslow = bt.indicators.SMA(period=self.p.pslow)
        self.cover = bt.indicators.CrossOver(self.sfast, self.sslow)
        if self.p.short:
            self.signal_add(bt.SIGNAL_LONGSHORT, self.cover)
        else:
            self.signal_add(bt.SIGNAL_LONG, self.cover)

    def start(self):
        super(self.__class__, self).start()
        if self.p.printdata:
            txtfields = list()
            txtfields.append('Len')
            txtfields.append('Datetime')
            txtfields.append('Open')
            txtfields.append('High')
            txtfields.append('Low')
            txtfields.append('Close')
            txtfields.append('Volume')
            txtfields.append('OpenInterest')
            print(','.join(txtfields))

    def next(self):
        # Backtrader Studio: SignalStrategy already runs the signals before
        # next(); calling super().next() here recursed forever
        if self.p.printdata:
            # Print only 1st data ... is just a check that things are running
            txtfields = list()
            txtfields.append('%04d' % len(self))
            txtfields.append(self.data.datetime.datetime(0).isoformat())
            txtfields.append('%.2f' % self.data0.open[0])
            txtfields.append('%.2f' % self.data0.high[0])
            txtfields.append('%.2f' % self.data0.low[0])
            txtfields.append('%.2f' % self.data0.close[0])
            txtfields.append('%.2f' % self.data0.volume[0])
            txtfields.append('%.2f' % self.data0.openinterest[0])
            print(','.join(txtfields))


_TFRAMES = collections.OrderedDict(
    (
        ('minutes', bt.TimeFrame.Minutes),
        ('days', bt.TimeFrame.Days),
        ('weeks', bt.TimeFrame.Weeks),
        ('months', bt.TimeFrame.Months),
        ('years', bt.TimeFrame.Years),
    )
)

_TFS = _TFRAMES.keys()


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='nvda-1999-2014.txt',
    fromdate='2013-01-01',
    todate='2014-12-31',
    cash=50000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 10},
)

OPTIONS = dict(
    pyfolio=True,
    pftimeframe='days',
)

CHOICES = dict(
    pftimeframe=['minutes', 'days', 'weeks', 'months', 'years'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Years)
    cerebro.addanalyzer(bt.analyzers.SQN)
    if o.pyfolio:
        cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio',
                            timeframe=_TFRAMES[o.pftimeframe])
