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
'''Trading calendars: a daily data resampled to weeks/months/years
with a calendar telling backtrader which days are trading days, so the
resampled bar can be delivered at the right moment. owncal uses the NYSE
2016 holidays defined here; pandascal needs pandas_market_calendars. The
sample downloaded YHOO for 2016 (no longer listed): SPY is used instead.

Ported from backtrader/samples/tradingcalendar/tcal.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt


class NYSE_2016(bt.TradingCalendar):
    params = dict(
        holidays=[
            datetime.date(2016, 1, 1),
            datetime.date(2016, 1, 18),
            datetime.date(2016, 2, 15),
            datetime.date(2016, 3, 25),
            datetime.date(2016, 5, 30),
            datetime.date(2016, 7, 4),
            datetime.date(2016, 9, 5),
            datetime.date(2016, 11, 24),
            datetime.date(2016, 12, 26),
        ]
    )


class St(bt.Strategy):
    params = dict(
    )

    def __init__(self):
        pass

    def start(self):
        self.t0 = datetime.datetime.utcnow()

    def stop(self):
        t1 = datetime.datetime.utcnow()
        print('Duration:', t1 - self.t0)

    def prenext(self):
        self.next()

    def next(self):
        print('Strategy len {} datetime {}'.format(
            len(self), self.datetime.date()), end=' ')

        print('Data0 len {} datetime {}'.format(
            len(self.data0), self.data0.datetime.date()), end=' ')

        if len(self.data1):
            print('Data1 len {} datetime {}'.format(
                len(self.data1), self.data1.datetime.date()))
        else:
            print()


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yahoo:SPY',
    fromdate='2016-01-01',
    todate='2016-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    timeframe='Weeks',
    owncal=False,
    pandascal='',
)

CHOICES = dict(
    timeframe=['Weeks', 'Months', 'Years'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data)
    d1 = cerebro.resampledata(data,
                              timeframe=getattr(bt.TimeFrame, o.timeframe))
    d1.plotinfo.plotmaster = data
    d1.plotinfo.sameaxis = True
    if o.pandascal:
        cerebro.addcalendar(o.pandascal)
    elif o.owncal:
        cerebro.addcalendar(NYSE_2016)
