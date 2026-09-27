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
'''Parabolic SAR on 5-minute data and on the same data resampled to
15 minutes.

Ported from backtrader/samples/psar/psar-intraday.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime

import backtrader as bt


class St(bt.Strategy):
    params = (
    )

    def __init__(self):
        self.psar0 = bt.ind.ParabolicSAR(self.data0)
        self.psar1 = bt.ind.ParabolicSAR(self.data1)
        pass

    def next(self):
        txt = []
        txt.append('{:04d}'.format(len(self)))
        txt.append('{:04d}'.format(len(self.data0)))
        txt.append(self.data0.datetime.datetime())
        txt.append('{:.2f}'.format(self.data0.close[0]))
        txt.append('PSAR')
        txt.append('{:04.2f}'.format(self.psar0[0]))
        if len(self.data1):
            txt.append('{:04d}'.format(len(self.data1)))
            txt.append(self.data1.datetime.datetime())
            txt.append('{:.2f}'.format(self.data1.close[0]))
            txt.append('PSAR')
            txt.append('{:04.2f}'.format(self.psar1[0]))

        print(','.join(str(x) for x in txt))


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


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    data = ctx.make_data(timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)
