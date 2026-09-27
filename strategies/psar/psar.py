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
'''Parabolic SAR on daily data.

Ported from backtrader/samples/psar/psar.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime

import backtrader as bt


class St(bt.Strategy):
    params = (
    )

    def __init__(self):
        self.psar = bt.ind.ParabolicSAR(period=20)
        pass

    def next(self):
        txt = ['{:4d}'.format(len(self))]
        txt.append('{}'.format(self.datetime.date()))
        txt.append('{:.2f}'.format(self.psar[0]))
        print(','.join(txt))


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
