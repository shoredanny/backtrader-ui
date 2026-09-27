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
'''Credit interest charged on short (and optionally long) positions.
A signal strategy goes long/short on an SMA crossover; set the yearly
interest rate in the sample options and compare the P&L.

Ported from backtrader/samples/credit-interest/credit-interest.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
import datetime
import itertools

import backtrader as bt


class SMACrossOver(bt.Signal):
    params = (('p1', 10), ('p2', 30),)

    def __init__(self):
        sma1 = bt.indicators.SMA(period=self.p.p1)
        sma2 = bt.indicators.SMA(period=self.p.p2)
        self.lines.signal = bt.indicators.CrossOver(sma1, sma2)


class NoExit(bt.Signal):
    def next(self):
        self.lines.signal[0] = 0.0


class St(bt.SignalStrategy):
    # Backtrader Studio: the signals were added with cerebro.add_signal in
    # the sample; they are created here from the params instead
    params = dict(period1=10, period2=30, signal='longshort', no_exit=False)

    opcounter = itertools.count(1)

    def __init__(self):
        sigtype = dict(longshort=bt.signal.SIGNAL_LONGSHORT,
                       long=bt.signal.SIGNAL_LONG,
                       short=bt.signal.SIGNAL_SHORT)[self.p.signal]
        self.signal_add(sigtype, SMACrossOver(p1=self.p.period1,
                                              p2=self.p.period2))
        if self.p.no_exit:
            if self.p.signal == 'long':
                self.signal_add(bt.signal.SIGNAL_LONGEXIT, NoExit())
            elif self.p.signal == 'short':
                self.signal_add(bt.signal.SIGNAL_SHORTEXIT, NoExit())

    def notify_order(self, order):
        if order.status == bt.Order.Completed:
            t = ''
            t += '{:02d}'.format(next(self.opcounter))
            t += ' {}'.format(order.data.datetime.datetime())
            t += ' BUY ' * order.isbuy() or ' SELL'
            t += ' Size: {:+d} / Price: {:.2f}'
            print(t.format(order.executed.size, order.executed.price))

    def notify_trade(self, trade):
        if trade.isclosed:
            print('Trade closed with P&L: Gross {} Net {}'.format(
                trade.pnl, trade.pnlcomm))


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
    sizer={'type': 'fixed', 'value': 10},
)

OPTIONS = dict(
    interest=0.0,
    interest_long=False,
    int2pnl=True,
    stocklike=False,
    margin=0.0,
    mult=1.0,
)

CHOICES = dict(
    signal=['longshort', 'long', 'short'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data)
    cerebro.broker.set_int2pnl(o.int2pnl)
    comminfo = bt.CommissionInfo(mult=o.mult, margin=o.margin,
                                 stocklike=o.stocklike, interest=o.interest,
                                 interest_long=o.interest_long)
    cerebro.broker.addcommissioninfo(comminfo)
