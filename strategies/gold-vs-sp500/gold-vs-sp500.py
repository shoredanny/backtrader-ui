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
'''Gold vs the S&P 500: weekly moving averages of both plus their
rolling Pearson correlation and the LogReturns2 observer. data0 is the
selected feed (SPY by default) and data1 is downloaded from Yahoo (option
"data1").

scipy is not installed in the backtrader env, so the correlation falls back
to numpy.corrcoef (same result).

Ported from backtrader/samples/gold-vs-sp500/gold-vs-sp500.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# Reference
# https://estrategiastrading.com/oro-bolsa-estadistica-con-python/

import datetime

try:
    import scipy.stats
except ImportError:  # Backtrader Studio: numpy fallback for the correlation
    scipy = None
import numpy

import backtrader as bt


class PearsonR(bt.ind.PeriodN):
    _mindatas = 2  # hint to the platform

    lines = ('correlation',)
    params = (('period', 20),)

    def next(self):
        x = self.data0.get(size=self.p.period)
        y = self.data1.get(size=self.p.period)
        if scipy is not None:
            c, p = scipy.stats.pearsonr(x, y)
        else:
            c = numpy.corrcoef(list(x), list(y))[0][1]

        self.lines.correlation[0] = c


class MACrossOver(bt.Strategy):
    params = (
        ('ma', bt.ind.MovAv.SMA),
        ('pd1', 20),
        ('pd2', 20),
    )

    def __init__(self):
        ma1 = self.p.ma(self.data0, period=self.p.pd1, subplot=True)
        self.p.ma(self.data1, period=self.p.pd2, plotmaster=ma1)
        PearsonR(self.data0, self.data1)


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yahoo:SPY',
    fromdate='2005-01-01',
    todate='2016-01-01',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    data1='GLD',
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    data1 = ctx.load('yahoo:' + ctx.opts.data1)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks)
    cerebro.resampledata(data1, timeframe=bt.TimeFrame.Weeks)
    data1.plotinfo.plotmaster = data
    cerebro.addobserver(bt.observers.LogReturns2,
                        timeframe=bt.TimeFrame.Weeks, compression=20)
