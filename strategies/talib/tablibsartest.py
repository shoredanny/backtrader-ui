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
'''TA-Lib's SAR next to backtrader's own ParabolicSAR.

Needs the TA-Lib Python package (not installed in the backtrader env:
`pip install TA-Lib`, which needs the TA-Lib C library).

Ported from backtrader/samples/talib/tablibsartest.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt


class TALibStrategy(bt.Strategy):
    def __init__(self):
        bt.talib.SAR(self.data.high, self.data.low)
        bt.ind.PSAR()


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='yhoo-1996-2015.txt',
    fromdate='2005-01-01',
    todate='2006-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    use_next=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    if not hasattr(bt.talib, 'SMA'):
        raise ImportError('TA-Lib is not installed in the backtrader env: '
                          'pip install TA-Lib (needs the TA-Lib C library)')
    cerebro.adddata(data)
    cerebro.p.runonce = not ctx.opts.use_next
