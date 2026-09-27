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
'''"Buy the f... dip": enter when the bar falls more than `fall`
(measured with `approach`), hold for `hold` bars, trading with 2x leverage
and cheat-on-close. The ValueUnlever observer shows the leveraged value and
the unleveraged asset curve.

Ported from backtrader/samples/btfd/btfd.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# References:
#  - https://www.reddit.com/r/algotrading/comments/5jez2b/can_anyone_replicate_this_strategy/
#  - http://dark-bid.com/BTFD-only-strategy-that-matters.html

import datetime

import backtrader as bt


class ValueUnlever(bt.observers.Value):
    '''Extension of regular Value observer to add leveraged view'''
    lines = ('value_lever', 'asset')
    params = (('assetstart', 100000.0), ('lever', True),)

    def next(self):
        super(ValueUnlever, self).next()
        if self.p.lever:
            self.lines.value_lever[0] = self._owner.broker._valuelever

        if len(self) == 1:
            self.lines.asset[0] = self.p.assetstart
        else:
            change = self.data[0] / self.data[-1]
            self.lines.asset[0] = change * self.lines.asset[-1]


class St(bt.Strategy):
    params = (
        ('fall', -0.01),
        ('hold', 2),
        ('approach', 'highlow'),
        ('target', 1.0),
        ('prorder', False),
        ('prtrade', False),
        ('prdata', False),
    )

    def __init__(self):
        if self.p.approach == 'closeclose':
            self.pctdown = self.data.close / self.data.close(-1) - 1.0
        elif self.p.approach == 'openclose':
            self.pctdown = self.data.close / self.data.open - 1.0
        elif self.p.approach == 'highclose':
            self.pctdown = self.data.close / self.data.high - 1.0
        elif self.p.approach == 'highlow':
            self.pctdown = self.data.low / self.data.high - 1.0

    def next(self):
        if self.position:
            if len(self) == self.barexit:
                self.close()
                if self.p.prdata:
                    print(','.join(str(x) for x in
                                   ['DATA', 'CLOSE',
                                    self.data.datetime.date().isoformat(),
                                    self.data.close[0],
                                    float('NaN')]))
        else:
            if self.pctdown <= self.p.fall:
                self.order_target_percent(target=self.p.target)
                self.barexit = len(self) + self.p.hold

                if self.p.prdata:
                    print(','.join(str(x) for x in
                                   ['DATA', 'OPEN',
                                    self.data.datetime.date().isoformat(),
                                    self.data.close[0],
                                    self.pctdown[0]]))

    def start(self):
        if self.p.prtrade:
            print(','.join(
                ['TRADE', 'Status', 'Date', 'Value', 'PnL', 'Commission']))
        if self.p.prorder:
            print(','.join(
                ['ORDER', 'Type', 'Date', 'Price', 'Size', 'Commission']))
        if self.p.prdata:
            print(','.join(['DATA', 'Action', 'Date', 'Price', 'PctDown']))

    def notify_order(self, order):
        if order.status in [order.Margin, order.Rejected, order.Canceled]:
            print('ORDER FAILED with status:', order.getstatusname())
        elif order.status == order.Completed:
            if self.p.prorder:
                print(','.join(map(str, [
                    'ORDER', 'BUY' * order.isbuy() or 'SELL',
                    self.data.num2date(order.executed.dt).date().isoformat(),
                    order.executed.price,
                    order.executed.size,
                    order.executed.comm,
                ]
                )))

    def notify_trade(self, trade):
        if not self.p.prtrade:
            return

        if trade.isclosed:
            print(','.join(map(str, [
                'TRADE', 'CLOSE',
                self.data.num2date(trade.dtclose).date().isoformat(),
                trade.value,
                trade.pnl,
                trade.commission,
            ]
            )))
        elif trade.justopened:
            print(','.join(map(str, [
                'TRADE', 'OPEN',
                self.data.num2date(trade.dtopen).date().isoformat(),
                trade.value,
                trade.pnl,
                trade.commission,
            ]
            )))


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yahoo:^GSPC',
    fromdate='1990-01-01',
    todate='2016-10-01',
    cash=100000.0,
    commission=0.0,
    slippage=0.0,
    coc=True,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    leverage=2.0,
    assetstart=100000.0,
)

CHOICES = dict(
    approach=['closeclose', 'openclose', 'highclose', 'highlow'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    cerebro.adddata(data)
    cerebro.broker.set_coc(True)
    cerebro.broker.setcommission(leverage=ctx.opts.leverage)
    cerebro.addobserver(ValueUnlever, assetstart=ctx.opts.assetstart)
