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
'''Interactive Brokers test strategy: logs every bar and, with
`trade`, enters with the configured order type (market, limit, stop trail,
bracket, OCA ...) and scales out.

Backtrader Studio runs this on historical data: the broker is the backtest
broker and, as no data ever turns LIVE, the param `backtest` (added in the
port) makes the strategy trade as if it were live. `trade` is enabled by
default in the form.

Ported from backtrader/samples/ibtest/ibtest.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

# The above could be sent to an independent module
import backtrader as bt
from backtrader.utils import flushfile  # win32 quick stdout flushing


class TestStrategy(bt.Strategy):
    params = dict(
        smaperiod=5,
        trade=False,
        stake=10,
        exectype=bt.Order.Market,
        stopafter=0,
        valid=None,
        cancel=0,
        donotsell=False,
        stoptrail=False,
        stoptraillimit=False,
        trailamount=None,
        trailpercent=None,
        limitoffset=None,
        oca=False,
        bracket=False,
        backtest=True,  # Backtrader Studio: act as if data were live
    )

    def __init__(self):
        # To control operation entries
        self.orderid = list()
        self.order = None

        self.counttostop = 0
        self.datastatus = 0

        # Create SMA on 2nd data
        self.sma = bt.indicators.MovAv.SMA(self.data, period=self.p.smaperiod)

        print('--------------------------------------------------')
        print('Strategy Created')
        print('--------------------------------------------------')

    def notify_data(self, data, status, *args, **kwargs):
        print('*' * 5, 'DATA NOTIF:', data._getstatusname(status), *args)
        if status == data.LIVE:
            self.counttostop = self.p.stopafter
            self.datastatus = 1

    def notify_store(self, msg, *args, **kwargs):
        print('*' * 5, 'STORE NOTIF:', msg)

    def notify_order(self, order):
        if order.status in [order.Completed, order.Cancelled, order.Rejected]:
            self.order = None

        print('-' * 50, 'ORDER BEGIN', datetime.datetime.now())
        print(order)
        print('-' * 50, 'ORDER END')

    def notify_trade(self, trade):
        print('-' * 50, 'TRADE BEGIN', datetime.datetime.now())
        print(trade)
        print('-' * 50, 'TRADE END')

    def prenext(self):
        self.next(frompre=True)

    def next(self, frompre=False):
        txt = list()
        txt.append('Data0')
        txt.append('%04d' % len(self.data0))
        dtfmt = '%Y-%m-%dT%H:%M:%S.%f'
        txt.append('{}'.format(self.data.datetime[0]))
        txt.append('%s' % self.data.datetime.datetime(0).strftime(dtfmt))
        txt.append('{}'.format(self.data.open[0]))
        txt.append('{}'.format(self.data.high[0]))
        txt.append('{}'.format(self.data.low[0]))
        txt.append('{}'.format(self.data.close[0]))
        txt.append('{}'.format(self.data.volume[0]))
        txt.append('{}'.format(self.data.openinterest[0]))
        txt.append('{}'.format(self.sma[0]))
        print(', '.join(txt))

        if len(self.datas) > 1 and len(self.data1):
            txt = list()
            txt.append('Data1')
            txt.append('%04d' % len(self.data1))
            dtfmt = '%Y-%m-%dT%H:%M:%S.%f'
            txt.append('{}'.format(self.data1.datetime[0]))
            txt.append('%s' % self.data1.datetime.datetime(0).strftime(dtfmt))
            txt.append('{}'.format(self.data1.open[0]))
            txt.append('{}'.format(self.data1.high[0]))
            txt.append('{}'.format(self.data1.low[0]))
            txt.append('{}'.format(self.data1.close[0]))
            txt.append('{}'.format(self.data1.volume[0]))
            txt.append('{}'.format(self.data1.openinterest[0]))
            txt.append('{}'.format(float('NaN')))
            print(', '.join(txt))

        if self.counttostop:  # stop after x live lines
            self.counttostop -= 1
            if not self.counttostop:
                self.env.runstop()
                return

        if not self.p.trade:
            return

        if self.datastatus and not self.position and len(self.orderid) < 1:
            exectype = self.p.exectype if not self.p.oca else bt.Order.Limit
            close = self.data0.close[0]
            price = round(close * 0.90, 2)
            self.order = self.buy(size=self.p.stake,
                                  exectype=exectype,
                                  price=price,
                                  valid=self.p.valid,
                                  transmit=not self.p.bracket)

            self.orderid.append(self.order)

            if self.p.bracket:
                # low side
                self.sell(size=self.p.stake,
                          exectype=bt.Order.Stop,
                          price=round(price * 0.90, 2),
                          valid=self.p.valid,
                          transmit=False,
                          parent=self.order)

                # high side
                self.sell(size=self.p.stake,
                          exectype=bt.Order.Limit,
                          price=round(close * 1.10, 2),
                          valid=self.p.valid,
                          transmit=True,
                          parent=self.order)

            elif self.p.oca:
                self.buy(size=self.p.stake,
                         exectype=bt.Order.Limit,
                         price=round(self.data0.close[0] * 0.80, 2),
                         oco=self.order)

            elif self.p.stoptrail:
                self.sell(size=self.p.stake,
                          exectype=bt.Order.StopTrail,
                          # price=round(self.data0.close[0] * 0.90, 2),
                          valid=self.p.valid,
                          trailamount=self.p.trailamount,
                          trailpercent=self.p.trailpercent)

            elif self.p.stoptraillimit:
                p = round(self.data0.close[0] - self.p.trailamount, 2)
                # p = self.data0.close[0]
                self.sell(size=self.p.stake,
                          exectype=bt.Order.StopTrailLimit,
                          price=p,
                          plimit=p + self.p.limitoffset,
                          valid=self.p.valid,
                          trailamount=self.p.trailamount,
                          trailpercent=self.p.trailpercent)

        elif self.position.size > 0 and not self.p.donotsell:
            if self.order is None:
                self.order = self.sell(size=self.p.stake // 2,
                                       exectype=bt.Order.Market,
                                       price=self.data0.close[0])

        elif self.order is not None and self.p.cancel:
            if self.datastatus > self.p.cancel:
                self.cancel(self.order)

        if self.datastatus:
            self.datastatus += 1

    def start(self):
        if self.p.backtest:
            self.datastatus = 1
        if getattr(self.data0, 'contractdetails', None) is not None:
            print('Timezone from ContractDetails: {}'.format(
                  self.data0.contractdetails.m_timeZoneId))

        header = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume',
                  'OpenInterest', 'SMA']
        print(', '.join(header))

        self.done = False


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='orcl-2014.txt',
    fromdate='',
    todate='',
    cash=100000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
    params={'trade': True},
)
