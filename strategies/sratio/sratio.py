#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
'''How the Sharpe Ratio is calculated, step by step, for two annual
returns and a risk-free rate. The sample is plain Python; here the
calculation runs in the strategy's start() and prints to the Log tab.

Ported from backtrader/samples/sratio/sratio.py.
'''
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import itertools
import math
import operator
import sys


if sys.version_info.major == 2:
    map = itertools.imap


def average(x):
    return math.fsum(x) / len(x)


def variance(x):
    avgx = average(x)
    return list(map(lambda y: (y - avgx) ** 2, x))


def standarddev(x):
    return math.sqrt(average(variance(x)))


import backtrader as bt


class SharpeRatioSteps(bt.Strategy):
    '''Prints the Sharpe Ratio calculation of the sample (no trading)'''
    params = dict(ret1=0.023286, ret2=0.0257816485323, riskfreerate=0.01)

    def start(self):
        returns = [self.p.ret1, self.p.ret2]
        retfree = self.p.riskfreerate
        print('returns is:', returns, ' - retfree is:', retfree)

        # Directly from backtrader
        retfree = itertools.repeat(retfree)
        ret_free = map(operator.sub, returns, retfree)  # excess returns
        ret_free_avg = average(list(ret_free))  # mean of the excess returns
        print('returns excess mean:', ret_free_avg)

        retdev = standarddev(returns)  # standard deviation
        print('returns standard deviation:', retdev)

        ratio = ret_free_avg / retdev  # mean excess returns  / std deviation
        print('Sharpe Ratio is:', ratio)


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
