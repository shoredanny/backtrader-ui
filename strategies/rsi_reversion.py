import backtrader as bt


class RsiReversion(bt.Strategy):
    '''Buy when RSI is oversold, sell when it becomes overbought.'''
    params = dict(
        period=14,
        oversold=30.0,
        overbought=70.0,
        printlog=False,
    )

    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.period)

    def log(self, txt):
        if self.p.printlog:
            print('%s, %s' % (self.datas[0].datetime.date(0).isoformat(), txt))

    def notify_order(self, order):
        if order.status == order.Completed:
            side = 'BUY' if order.isbuy() else 'SELL'
            self.log('%s EXECUTED %.2f x %s' % (side, order.executed.price,
                                               order.executed.size))

    def next(self):
        if not self.position:
            if self.rsi < self.p.oversold:
                self.buy()
        elif self.rsi > self.p.overbought:
            self.close()
