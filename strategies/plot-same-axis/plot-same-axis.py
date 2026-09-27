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
'''Indicators created for plotting: SMA, MACD, Stochastic and RSI,
with params to plot some of them on the same axis as others (matplotlib
plotting options; Backtrader Studio shows each in its own panel).

Ported from backtrader/samples/plot-same-axis/plot-same-axis.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

# The above could be sent to an independent module
import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind


class PlotStrategy(bt.Strategy):
    '''
    The strategy does nothing but create indicators for plotting purposes
    '''
    params = dict(
        smasubplot=False,  # default for Moving averages
        nomacdplot=False,
        rsioverstoc=False,
        rsioversma=False,
        stocrsi=False,
        stocrsilabels=False,
    )

    def __init__(self):
        sma = btind.SMA(subplot=self.params.smasubplot)

        macd = btind.MACD()
        # In SMA we passed plot directly as kwarg, here the plotinfo.plot
        # attribute is changed - same effect
        macd.plotinfo.plot = not self.params.nomacdplot

        # Let's put rsi on stochastic/sma or the other way round
        stoc = btind.Stochastic()
        rsi = btind.RSI()
        if self.params.stocrsi:
            stoc.plotinfo.plotmaster = rsi
            stoc.plotinfo.plotlinelabels = self.p.stocrsilabels
        elif self.params.rsioverstoc:
            rsi.plotinfo.plotmaster = stoc
        elif self.params.rsioversma:
            rsi.plotinfo.plotmaster = sma


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-day-001.txt',
    fromdate='2006-01-01',
    todate='2006-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)
