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
'''A PandasData subclass with extra lines (optix_close, optix_pess,
optix_opt) read from a DataFrame. Reads the selected file with pandas; it
needs the optix columns, as in 2006-day-001-optix.txt.

Ported from backtrader/samples/data-pandas/data-pandas-optix.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import backtrader as bt
import backtrader.feeds as btfeeds

import pandas


class PandasDataOptix(btfeeds.PandasData):

    lines = ('optix_close', 'optix_pess', 'optix_opt',)
    params = (('optix_close', -1),
              ('optix_pess', -1),
              ('optix_opt', -1))

    if False:
        # No longer needed with version 1.9.62.122
        datafields = btfeeds.PandasData.datafields + (
            ['optix_close', 'optix_pess', 'optix_opt'])


class StrategyOptix(bt.Strategy):

    def next(self):
        print('%03d %f %f, %f' % (
            len(self),
            self.data.optix_close[0],
            self.data.lines.optix_pess[0],
            self.data.optix_opt[0],))


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-day-001-optix.txt',
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
                else ctx.datapath('2006-day-001-optix.txt'))
    skiprows = 1 if o.noheaders else 0
    header = None if o.noheaders else 0
    dataframe = pandas.read_csv(datapath, skiprows=skiprows, header=header,
                                parse_dates=True, index_col=0)
    if not o.noprint:
        print('--------------------------------------------------')
        print(dataframe)
        print('--------------------------------------------------')
    cerebro.adddata(PandasDataOptix(dataname=dataframe))
