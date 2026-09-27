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
'''Renko bricks made with the Renko filter, either replacing the data
or (dual) as a second data next to it, with an RSI on each. renko takes the
filter kwargs, e.g. size=5 or autosize=10.

Ported from backtrader/samples/renko/renko.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

import backtrader as bt


class St(bt.Strategy):
    params = dict(
    )

    def __init__(self):
        for d in self.datas:
            bt.ind.RSI(d)

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

OPTIONS = dict(
    renko='',
    dual=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    fkwargs = eval('dict(' + o.renko + ')')
    if not o.dual:
        data.addfilter(bt.filters.Renko, **fkwargs)
        cerebro.adddata(data)
    else:
        cerebro.adddata(data)
        data1 = data.clone()
        data1.addfilter(bt.filters.Renko, **fkwargs)
        cerebro.adddata(data1)
