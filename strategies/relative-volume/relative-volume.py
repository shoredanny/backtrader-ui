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
'''RelativeVolumeByBar (relvolbybar.py): the volume of each intraday
bar relative to the same bar of the previous session.

Ported from backtrader/samples/relative-volume/relative-volume.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime

# The above could be sent to an independent module
import backtrader as bt
import backtrader.feeds as btfeeds

from relvolbybar import RelativeVolumeByBar


class St(bt.Strategy):
    '''Empty strategy: the sample is about the indicator'''


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
    prestart='08:00',
    start='09:15',
    end='17:15',
    writer=False,
    wrcsv=False,
)


def configure(cerebro, data, ctx):
    '''Set up cerebro like the sample's runstrat()'''
    o = ctx.opts
    cerebro.adddata(data)
    totime = lambda s: datetime.datetime.strptime(s, '%H:%M').time()
    cerebro.addindicator(RelativeVolumeByBar, prestart=totime(o.prestart),
                         start=totime(o.start), end=totime(o.end))
    if ctx.opts.writer:
        cerebro.addwriter(bt.WriterFile, csv=ctx.opts.wrcsv)
