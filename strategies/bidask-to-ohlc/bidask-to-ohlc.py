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
'''Turns bid/ask ticks into OHLC bars: a GenericCSVData maps the
"offer" column to open/high/low/close and resampledata() compresses ticks.

Uses its own data file (option "data", from backtrader/datas); the data feed
and dates selected in the form are ignored. Output is in the Log tab.

Ported from backtrader/samples/bidask-to-ohlc/bidask-to-ohlc.py.
'''
from __future__ import (absolute_import, division, print_function,)
#                        unicode_literals)

import datetime

import backtrader as bt
import backtrader.feeds as btfeeds


class St(bt.Strategy):
    def next(self):
        print(','.join(str(x) for x in [
            self.data.datetime.datetime(),
            self.data.open[0], self.data.high[0],
            self.data.high[0], self.data.close[0],
            self.data.volume[0]]))


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-day-001.txt',
    fromdate='',
    todate='',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    data='bidask2.csv',
    compression=2,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
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
