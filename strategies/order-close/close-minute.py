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
'''Order.Close execution: orders are matched with the closing
price of the session. With `eosbar` the broker treats a bar at the session
end time as the close of the session. Enters and exits every two days on intraday data.

Ported from backtrader/samples/order-close/close-minute.py.
'''
from __future__ import (absolute_import, division, print_function,)
#                        unicode_literals)

import datetime

import backtrader as bt
import backtrader.feeds as btfeeds


class St(bt.Strategy):
    def __init__(self):
        self.curdate = datetime.date.min
        self.elapsed = 0
        self.order = None

    def notify_order(self, order):
        curdtstr = self.data.datetime.datetime().strftime('%a %Y-%m-%d %H:%M:%S')
        if order.status in [order.Completed]:
            dtstr = bt.num2date(order.executed.dt).strftime('%a %Y-%m-%d %H:%M:%S')
            if order.isbuy():
                print('%s: BUY  EXECUTED, on:' % curdtstr, dtstr)
                self.order = None
            else:  # Sell
                print('%s: SELL EXECUTED, on:' % curdtstr, dtstr)

    def next(self):
        curdate = self.data.datetime.date()
        if curdate > self.curdate:
            self.elapsed += 1
            self.curdate = curdate

        dtstr = self.data.datetime.datetime().strftime('%a %Y-%m-%d %H:%M:%S')
        if self.position and self.elapsed == 2:
            print('%s: SELL CREATED' % dtstr)
            self.close(exectype=bt.Order.Close)
            self.elapsed = 0
        elif self.order is None and self.elapsed == 2:  # no pending order
            print('%s: BUY  CREATED' % dtstr)
            self.order = self.buy(exectype=bt.Order.Close)
            self.elapsed = 0


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-min-005.txt',
    fromdate='',
    todate='',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    eosbar=False,
    tend='',
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    if o.tend:
        data = ctx.make_data(
            sessionend=datetime.datetime.strptime(o.tend, '%H:%M'))
    cerebro.adddata(data)
    if o.eosbar:
        cerebro.broker.seteosbar(True)
