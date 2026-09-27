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
'''TimeReturn and SharpeRatio analyzers over a timeframe (with
riskfreerate, annualize, factor ... from the options) on the built-in
SMA_CrossOver strategy. A WriterFile summary is printed in the Log tab.

Ported from backtrader/samples/sharpe-timereturn/sharpe-timereturn.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt


class SmaCrossOver(bt.strategies.MA_CrossOver):
    '''backtrader's built-in SMA_CrossOver (MA_CrossOver) strategy, which
    the sample adds with cerebro.addstrategy(bt.strategies.SMA_CrossOver)'''


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2005-2006-day-001.txt',
    fromdate='2005-01-01',
    todate='2006-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    tframe='years',
    annualize=False,
    riskfreerate=None,
    factor=None,
    stddev_sample=False,
    no_convertrate=False,
    writercsv=False,
)

CHOICES = dict(
    tframe=['days', 'weeks', 'months', 'years'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
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
