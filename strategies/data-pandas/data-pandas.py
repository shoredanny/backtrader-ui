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
'''Loading a pandas DataFrame into backtrader with PandasData
(nocase=True matches the column names case-insensitively). The selected CSV
file is read with pandas and printed to the Log tab.

Ported from backtrader/samples/data-pandas/data-pandas.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import backtrader as bt
import backtrader.feeds as btfeeds

import pandas


class St(bt.Strategy):
    '''Empty strategy: the sample is about the pandas data feed'''


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-day-001.txt',
    fromdate='',
    todate='',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    noheaders=False,
    noprint=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    datapath = (ctx.feed['path'] if ctx.feed['type'] == 'file'
                else ctx.datapath('2006-day-001.txt'))
    skiprows = 1 if o.noheaders else 0
    header = None if o.noheaders else 0
    dataframe = pandas.read_csv(datapath, skiprows=skiprows, header=header,
                                parse_dates=True, index_col=0)
    if not o.noprint:
        print('--------------------------------------------------')
        print(dataframe)
        print('--------------------------------------------------')
    cerebro.adddata(bt.feeds.PandasData(dataname=dataframe, nocase=True))
