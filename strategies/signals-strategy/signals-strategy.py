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
'''Signals: the close minus its SMA as the main signal (long/short,
long only or short only) plus an optional exit signal made from two SMAs.
The sample fed them to cerebro.add_signal(); here SignalsStrategy adds them
from its params.

Ported from backtrader/samples/signals-strategy/signals-strategy.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
import datetime

import backtrader as bt

MAINSIGNALS = collections.OrderedDict(
    (('longshort', bt.SIGNAL_LONGSHORT),
     ('longonly', bt.SIGNAL_LONG),
     ('shortonly', bt.SIGNAL_SHORT),)
)


EXITSIGNALS = {
    'longexit': bt.SIGNAL_LONGEXIT,
    'shortexit': bt.SIGNAL_LONGEXIT,
}


class SMACloseSignal(bt.Indicator):
    lines = ('signal',)
    params = (('period', 30),)

    def __init__(self):
        self.lines.signal = self.data - bt.indicators.SMA(period=self.p.period)


class SMAExitSignal(bt.Indicator):
    lines = ('signal',)
    params = (('p1', 5), ('p2', 30),)

    def __init__(self):
        sma1 = bt.indicators.SMA(period=self.p.p1)
        sma2 = bt.indicators.SMA(period=self.p.p2)
        self.lines.signal = sma1 - sma2


class SignalsStrategy(bt.SignalStrategy):
    '''SignalStrategy fed with the sample's signals (what cerebro builds
    for cerebro.add_signal)'''
    params = dict(signal='longshort', smaperiod=30, exitsignal='',
                  exitperiod=5)

    def __init__(self):
        self.signal_add(MAINSIGNALS[self.p.signal],
                        SMACloseSignal(period=self.p.smaperiod))
        if self.p.exitsignal:
            self.signal_add(EXITSIGNALS[self.p.exitsignal],
                            SMAExitSignal(p1=self.p.exitperiod,
                                          p2=self.p.smaperiod))


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2005-2006-day-001.txt',
    fromdate='',
    todate='',
    cash=50000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

CHOICES = dict(
    signal=['longshort', 'longonly', 'shortonly'],
    exitsignal=['', 'longexit', 'shortexit'],
)
