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
'''Variability-Weighted Return (VWR) next to Returns, SQN,
SharpeRatio_A and monthly/yearly TimeReturn, on the built-in SMA_CrossOver
strategy (see the Analyzers tab and the WriterFile summary in Log).

Ported from backtrader/samples/vwr/vwr.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt

TFRAMES = dict(
    days=bt.TimeFrame.Days,
    weeks=bt.TimeFrame.Weeks,
    months=bt.TimeFrame.Months,
    years=bt.TimeFrame.Years)


class SmaCrossOver(bt.strategies.MA_CrossOver):
    '''backtrader's built-in SMA_CrossOver (MA_CrossOver) strategy, which
    the sample adds with cerebro.addstrategy(bt.strategies.SMA_CrossOver)'''


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2005-2006-day-001.txt',
    fromdate='',
    todate='',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    tframe='',
    tann=None,
    sigma_max=None,
    tau=None,
    writercsv=False,
)

CHOICES = dict(
    tframe=['', 'days', 'weeks', 'months', 'years'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
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
