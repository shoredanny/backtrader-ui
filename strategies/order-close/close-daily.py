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
end time as the close of the session. Random entries: every run differs.

Ported from backtrader/samples/order-close/close-daily.py.
'''
from __future__ import (absolute_import, division, print_function,)
#                        unicode_literals)

import datetime
import random

import backtrader as bt
import backtrader.feeds as btfeeds

from backtrader.utils.py3 import with_metaclass


class St(bt.Strategy):
    def __init__(self):
        self.order = None

    def notify_order(self, order):
        curdtstr = self.data.datetime.datetime().strftime('%a %Y-%m-%d')
        if order.status in [order.Completed]:
            dtstr = bt.num2date(order.executed.dt).strftime('%a %Y-%m-%d')
            if order.isbuy():
                print('%s: BUY  EXECUTED, on:' % curdtstr, dtstr)
            else:  # Sell
                print('%s: SELL EXECUTED, on:' % curdtstr, dtstr)

            self.order = None

    def next(self):
        dtstr = self.data.datetime.datetime().strftime('%a %Y-%m-%d %H:%M:%S')
        # print('%s: data' % dtstr)
        if self.order:
            return

        if not random.randint(0, 5):  # roll a dice to decide entering/exit
            if self.position:
                print('%s: SELL CREATED' % dtstr)
                self.order = self.close(exectype=bt.Order.Close)
            else:  # no pending order
                print('%s: BUY  CREATED' % dtstr)
                self.order = self.buy(exectype=bt.Order.Close)


class SessionEndFiller(with_metaclass(bt.metabase.MetaParams, object)):
    '''This data filter simply adds the time given in param ``endtime`` to the
    current data datetime

    It is intended for daily bars which come from sources with no time
    indication and can be used to signal the bar is passed the end of the
    session

    The default value for ``endtime`` is 1 second before midnight 23:59:59
    '''
    params = (('endtime', datetime.time(23, 59, 59)),)

    def __call__(self, data):
        '''
        Params:
          - data: the data source to filter/process

        Returns:
          - False (always) because this filter does not remove bars from the
            stream
        '''
        # Get time of current (from data source) bar
        dtime = datetime.datetime.combine(data.datetime.date(), self.p.endtime)
        data.datetime[0] = data.date2num(dtime)
        return False


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2005-2006-day-001.txt',
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
    filltime='',
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    if o.tend:
        data = ctx.make_data(
            sessionend=datetime.datetime.strptime(o.tend, '%H:%M'))
    if o.filltime:
        filltime = datetime.datetime.strptime(o.filltime, '%H:%M:%S').time()
        data.addfilter(SessionEndFiller, endtime=filltime)
    cerebro.adddata(data)
    if o.eosbar:
        cerebro.broker.seteosbar(True)
