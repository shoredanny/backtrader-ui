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
'''Volume filling: orders sized at a percentage of the bar volume are
filled completely, or partially by a filler (FixedSize, FixedBarPerc,
BarPointPerc; filler_args e.g. perc=50). Watch the partial executions in the
Log and Orders tabs.

Ported from backtrader/samples/volumefilling/volumefilling.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import os.path
import time
import sys


import backtrader as bt


class St(bt.Strategy):
    params = (
        ('stakeperc', 10.0),
        ('opbreak', 10),
    )

    def notify_order(self, order):
        print('-- NOTIFY ORDER BEGIN')
        print(order)
        print('-- NOTIFY ORDER END')
        print('-- ORDER REMSIZE:', order.executed.remsize)

        if order.status == order.Completed:
            print('++ ORDER COMPLETED at data.len:', len(order.data))
            self.doop = -self.p.opbreak

    def __init__(self):
        pass

    def start(self):
        self.callcounter = 0
        txtfields = list()
        txtfields.append('Len')
        txtfields.append('Datetime')
        txtfields.append('Open')
        txtfields.append('High')
        txtfields.append('Low')
        txtfields.append('Close')
        txtfields.append('Volume')
        txtfields.append('OpenInterest')
        print(','.join(txtfields))

        self.doop = 0

    def next(self):
        txtfields = list()
        txtfields.append('%04d' % len(self))
        txtfields.append(self.data0.datetime.date(0).isoformat())
        txtfields.append('%.2f' % self.data0.open[0])
        txtfields.append('%.2f' % self.data0.high[0])
        txtfields.append('%.2f' % self.data0.low[0])
        txtfields.append('%.2f' % self.data0.close[0])
        txtfields.append('%.2f' % self.data0.volume[0])
        txtfields.append('%.2f' % self.data0.openinterest[0])
        print(','.join(txtfields))

        # Single order
        if self.doop == 0:
            if not self.position.size:
                stakevol = (self.data0.volume[0] * self.p.stakeperc) // 100
                print('++ STAKE VOLUME:', stakevol)
                self.buy(size=stakevol)

            else:
                self.close()

        self.doop += 1


FILLERS = {
    'FixedSize': bt.broker.fillers.FixedSize,
    'FixedBarPerc': bt.broker.fillers.FixedBarPerc,
    'BarPointPerc': bt.broker.fillers.BarPointPerc,
}


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-volume-day-001.txt',
    fromdate='',
    todate='',
    cash=500000000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    filler='',
    filler_args='',
)

CHOICES = dict(
    filler=['', 'FixedSize', 'FixedBarPerc', 'BarPointPerc'],
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data)
    if o.filler:
        fillerkwargs = eval('dict(' + o.filler_args + ')')
        cerebro.broker.set_filler(FILLERS[o.filler](**fillerkwargs))
