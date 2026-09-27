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
'''Resampling tick data to larger timeframes (ticks, seconds,
minutes, ...). Reads the selected file as tick data (ticksample.csv by
default); bar2edge/adjbartime/rightedge control how bars are aligned.

Ported from backtrader/samples/resample-tickdata/resample-tickdata.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import backtrader as bt
import backtrader.feeds as btfeeds


class St(bt.Strategy):
    '''Empty strategy: the sample is about resampling ticks'''


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='ticksample.csv',
    fromdate='',
    todate='',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    timeframe='ticks',
    compression=1,
    nobar2edge=False,
    noadjbartime=False,
    rightedge=False,
    writer=False,
    wrcsv=False,
)

CHOICES = dict(
    timeframe=['ticks', 'microseconds', 'seconds', 'minutes', 'daily', 'weekly', 'monthly'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
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
    if ctx.opts.writer:
        cerebro.addwriter(bt.WriterFile, csv=ctx.opts.wrcsv)
