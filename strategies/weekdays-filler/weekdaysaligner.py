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
'''Aligning two datas with different trading days: WeekDaysFiller
(weekdaysfiller.py) adds the missing weekdays (NaN bars, or the last close
with fillclose). data0 is the selected feed; data1 is the file in the
"data1" option or a clone of data0.

Ported from backtrader/samples/weekdays-filler/weekdaysaligner.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind
import backtrader.utils.flushfile

# from wkdaysfiller import WeekDaysFiller
from weekdaysfiller import WeekDaysFiller


class St(bt.Strategy):
    params = (('sma', 0),)

    def __init__(self):
        if self.p.sma:
            btind.SMA(self.data0, period=self.p.sma)
            btind.SMA(self.data1, period=self.p.sma)

    def next(self):
        dtequal = (self.data0.datetime.datetime() ==
                   self.data1.datetime.datetime())

        txt = ''
        txt += '%04d, %5s' % (len(self), str(dtequal))
        txt += ', data0, %s' % self.data0.datetime.datetime().isoformat()
        txt += ', %s, data1' % self.data1.datetime.datetime().isoformat()
        print(txt)


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yhoo-1996-2014.txt',
    fromdate='2012-01-01',
    todate='2012-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    data1='orcl-1995-2014.txt',
    fillclose=False,
    filler=False,
    filler0=False,
    filler1=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    data1 = ctx.load(o.data1) if o.data1 else data.clone()
    if o.filler or o.filler0:
        data.addfilter(WeekDaysFiller, fillclose=o.fillclose)
    if o.filler or o.filler1:
        data1.addfilter(WeekDaysFiller, fillclose=o.fillclose)
    cerebro.adddata(data)
    cerebro.adddata(data1)
