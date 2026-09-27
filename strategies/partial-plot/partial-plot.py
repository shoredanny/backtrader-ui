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
'''Indicators on a daily data plus a weekly resampled copy (the
sample shows plotting only part of a run).

Ported from backtrader/samples/partial-plot/partial-plot.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime

import backtrader as bt


class St(bt.Strategy):
    params = (
    )

    def __init__(self):
        # self.schedule_once(self.pepe, when=datetime.datetime())
        # This one won't have the expected fidelity in backtesting
        # self.schedule_once(self.pepe, when=datetime.timedelta())
        # self.schedule_reps(self.pepe, when=datetime.time(), days=bt.sched.)

        bt.ind.SMA()
        stoc = bt.ind.Stochastic()
        bt.ind.CrossOver(stoc.lines.percK, stoc.lines.percD)

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


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks)
