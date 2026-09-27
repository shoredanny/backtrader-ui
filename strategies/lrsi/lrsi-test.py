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
'''Laguerre RSI on the mid price. The sample also used LaguerreRSI2
and LaguerreRSI3, which this backtrader version does not have; the
LaguerreFilter is shown instead.

Ported from backtrader/samples/lrsi/lrsi-test.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime

import backtrader as bt


class St(bt.Strategy):
    params = (
    )

    def __init__(self):
        mid = (self.data.high + self.data.low) / 2.0
        bt.ind.LaguerreRSI(mid)
        # Backtrader Studio: LaguerreRSI3/LaguerreRSI2 do not exist in this
        # backtrader version
        bt.ind.LaguerreFilter(mid)
        pass

    def next(self):
        pass


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
