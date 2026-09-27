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
'''Slippage: percentage (slip_perc) or fixed (slip_fixed) slippage
applied by the broker, with slip_open / slip_match / slip_out controlling
the details, on an SMA crossover signal strategy. Compare the prices in the
Log tab.

Ported from backtrader/samples/slippage/slippage.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
import datetime
import itertools

import backtrader as bt


class SMACrossOver(bt.Indicator):
    lines = ('signal',)
    params = (('p1', 10), ('p2', 30),)

    def __init__(self):
        sma1 = bt.indicators.SMA(period=self.p.p1)
        sma2 = bt.indicators.SMA(period=self.p.p2)
        self.lines.signal = bt.indicators.CrossOver(sma1, sma2)


class SlipSt(bt.SignalStrategy):
    # Backtrader Studio: the signal was added with cerebro.add_signal in the
    # sample; it is created here from the params instead
    params = dict(period1=10, period2=30, longonly=False)

    opcounter = itertools.count(1)

    def __init__(self):
        stype = (bt.signal.SIGNAL_LONG if self.p.longonly
                 else bt.signal.SIGNAL_LONGSHORT)
        self.signal_add(stype, SMACrossOver(p1=self.p.period1,
                                            p2=self.p.period2))

    def notify_order(self, order):
        if order.status == bt.Order.Completed:
            t = ''
            t += '{:02d}'.format(next(self.opcounter))
            t += ' {}'.format(order.data.datetime.datetime())
            t += ' BUY ' * order.isbuy() or ' SELL'
            t += ' Size: {:+d} / Price: {:.2f}'
            print(t.format(order.executed.size, order.executed.price))


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

OPTIONS = dict(
    slip_perc=None,
    slip_fixed=None,
    no_slip_match=False,
    slip_out=False,
    slip_open=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data)
    kwargs = dict(slip_open=o.slip_open, slip_match=not o.no_slip_match,
                  slip_out=o.slip_out)
    if o.slip_perc is not None:
        cerebro.broker.set_slippage_perc(float(o.slip_perc), **kwargs)
    elif o.slip_fixed is not None:
        cerebro.broker.set_slippage_fixed(float(o.slip_fixed), **kwargs)
