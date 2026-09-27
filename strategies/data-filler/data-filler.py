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
'''SessionFilter / SessionFiller: drop bars outside the trading
session and fill missing minute bars inside it. The optional RelativeVolume
indicator (relativevolume.py) compares each bar's volume with the same
moment of the previous session.

Ported from backtrader/samples/data-filler/data-filler.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import math

# The above could be sent to an independent module
import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.utils.flushfile
import backtrader.filters as btfilters

from relativevolume import RelativeVolume


class St(bt.Strategy):
    '''Empty strategy: the sample is about the data filters'''


# ---------------------------------------------------------------------------
# Backtrader Studio setup (replaces the sample's argparse / runstrat code)
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    feed='2006-01-02-volume-min-001.txt',
    fromdate='2006-01-01',
    todate='2006-12-31',
    cash=10000.0,
    commission=0.0,
    slippage=0.0,
    coc=False,
    sizer={'type': 'fixed', 'value': 1},
)

OPTIONS = dict(
    filter=False,
    filler=False,
    fvol=0.0,
    tstart='09:15',
    tend='17:15',
    relvol=False,
    writer=False,
    wrcsv=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    dtstart = datetime.datetime.strptime(o.tstart, '%H:%M')
    dtend = datetime.datetime.strptime(o.tend, '%H:%M')
    data = ctx.make_data(timeframe=bt.TimeFrame.Minutes, compression=1,
                         sessionstart=dtstart, sessionend=dtend)
    if o.filter:
        data.addfilter(btfilters.SessionFilter)
    if o.filler:
        data.addfilter(btfilters.SessionFiller, fill_vol=o.fvol)
    cerebro.adddata(data)
    if o.relvol:
        # + 1 to include last moment of the interval dstart <-> dtend
        td = ((dtend - dtstart).seconds // 60) + 1
        cerebro.addindicator(RelativeVolume, period=td,
                             volisnan=math.isnan(o.fvol))
    if ctx.opts.writer:
        cerebro.addwriter(bt.WriterFile, csv=ctx.opts.wrcsv)
