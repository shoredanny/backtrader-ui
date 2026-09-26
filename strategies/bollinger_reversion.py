import backtrader as bt


class BollingerReversion(bt.Strategy):
    '''Buy a close below the lower Bollinger band, exit at the middle band.'''
    params = dict(
        period=20,
        devfactor=2.0,
    )

    def __init__(self):
        self.bb = bt.ind.BollingerBands(period=self.p.period,
                                        devfactor=self.p.devfactor)

    def next(self):
        close = self.data.close[0]
        if not self.position:
            if close < self.bb.bot[0]:
                self.buy()
        elif close > self.bb.mid[0]:
            self.close()
