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
'''CalendarDays filter: fills the gaps of a daily feed so that every
calendar day (weekends and holidays included) has a bar. Enable the filter
with the "calendar" option and look at the chart/log.

Ported from backtrader/samples/calendar-days/calendar-days.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import backtrader.filters as btfilters


class St(bt.Strategy):
    '''Empty strategy (the sample adds no trading logic). The optional
    SMA shows how indicators behave over the filled days.'''
    params = dict(sma=False, period=15)

    def __init__(self):
        if self.p.sma:
            btind.SMA(period=self.p.period)


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-day-001.txt',
    fromdate='2006-01-01',
    todate='2006-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    calendar=False,
    fprice=None,
    fvol=0.0,
    writer=False,
    wrcsv=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    if o.calendar:
        # backtrader's filter compares fill_price > 0, which fails for None
        # on Python 3; 0 means the same: fill with the last close
        fprice = float(o.fprice) if o.fprice is not None else 0
        data.addfilter(btfilters.CalendarDays,
                       fill_price=fprice, fill_vol=o.fvol)
    cerebro.adddata(data)
    if ctx.opts.writer:
        cerebro.addwriter(bt.WriterFile, csv=ctx.opts.wrcsv)
