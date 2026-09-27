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
'''A data feed with a custom line hierarchy (bid/ask instead of OHLC)
and a strategy printing it. Uses its own file (option "data"); the selected
data feed and dates are ignored. The chart shows the bid line.

Ported from backtrader/samples/data-bid-ask/bidask.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind


class BidAskCSV(btfeeds.GenericCSVData):
    linesoverride = True  # discard usual OHLC structure
    # datetime must be present and last
    lines = ('bid', 'ask', 'datetime')
    # datetime (always 1st) and then the desired order for
    params = (
        # (datetime, 0), # inherited from parent class
        ('bid', 1),  # default field pos 1
        ('ask', 2),  # default field pos 2
    )


class St(bt.Strategy):
    params = (('sma', False), ('period', 3))

    def __init__(self):
        if self.p.sma:
            self.sma = btind.SMA(self.data, period=self.p.period)

    def next(self):
        dtstr = self.data.datetime.datetime().isoformat()
        txt = '%4d: %s - Bid %.4f - %.4f Ask' % (
            (len(self), dtstr, self.data.bid[0], self.data.ask[0]))

        if self.p.sma:
            txt += ' - SMA: %.4f' % self.sma[0]
        print(txt)


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
    params={'period': 5},
)

OPTIONS = dict(
    data='bidask.csv',
    dtformat='%m/%d/%Y %H:%M:%S',
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(BidAskCSV(dataname=ctx.datapath(o.data),
                              dtformat=o.dtformat,
                              timeframe=bt.TimeFrame.Ticks))
