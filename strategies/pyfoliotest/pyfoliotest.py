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
'''Random trading on three datas with the PyFolio analyzer collecting
returns, positions and transactions (shown in the Analyzers tab; pyfolio
itself is not installed, so no tear sheet). Random entries: every run
differs.

Ported from backtrader/samples/pyfoliotest/pyfoliotest.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime
import random

import backtrader as bt


class St(bt.Strategy):
    params = (
        ('printout', False),
        ('stake', 1000),
    )

    def __init__(self):
        pass

    def start(self):
        if self.p.printout:
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

    def next(self):
        if self.p.printout:
            # Print only 1st data ... is just a check that things are running
            txtfields = list()
            txtfields.append('%04d' % len(self))
            txtfields.append(self.data.datetime.datetime(0).isoformat())
            txtfields.append('%.2f' % self.data0.open[0])
            txtfields.append('%.2f' % self.data0.high[0])
            txtfields.append('%.2f' % self.data0.low[0])
            txtfields.append('%.2f' % self.data0.close[0])
            txtfields.append('%.2f' % self.data0.volume[0])
            txtfields.append('%.2f' % self.data0.openinterest[0])
            print(','.join(txtfields))

        # Data 0
        for data in self.datas:
            toss = random.randint(1, 10)
            curpos = self.getposition(data)
            if curpos.size:
                if toss > 5:
                    size = curpos.size // 2
                    self.sell(data=data, size=size)
                    if self.p.printout:
                        print('SELL {} @%{}'.format(size, data.close[0]))

            elif toss < 5:
                self.buy(data=data, size=self.p.stake)
                if self.p.printout:
                    print('BUY  {} @%{}'.format(self.p.stake, data.close[0]))


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yhoo-1996-2015.txt',
    fromdate='2005-01-01',
    todate='2006-12-31',
    cash=50000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    data1='orcl-1995-2014.txt',
    data2='nvda-1999-2014.txt',
    pyfolio=True,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data, name='Data0')
    cerebro.adddata(ctx.load(o.data1), name='Data1')
    cerebro.adddata(ctx.load(o.data2), name='Data2')
    if o.pyfolio:
        cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')
