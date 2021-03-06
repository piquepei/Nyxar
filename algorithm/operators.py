##############
# Efficient operators like SMA, EMA etc
# those operators are all sub-classes of a base operator
# which defines basic storage structure to enable efficient calculation of those indicators
# 1, initialize.
#   to construct an operator, we need to initialize basic parameters that define this operator
# 2, internal storage
#   stock indicators usually rely on price history, therefore we allow customized storage of price history
#   for each operator.
# 3, online calculation
#   calculation of indicators should be efficient: i.e. it only needs input of price of the current
#   time stamp, while utilizing its internal storage for necessary modifications. If necessary, a
#   @memorized or @lazy_evaluate might be used.
#############

from backtest.BackExchange import BackExchange
from core.Ticker import TickerFields

from collections import deque
import math


class OperatorsBase(object):
    def __init__(self, exchange: BackExchange):
        self.exchange = exchange
        self.last_timestamp = 0
        self.operator_name = ""
        pass

    def get(self):
        pass

    """
    This is something that should only be used internally, 
    but support is added here nevertheless to facilitate
    highly customized indicator of indicators, like RSI.
    in get_feed, every time stamp value is sent in directly 
    rather than read from the exchange
    """

    def __get_feed(self, value):
        pass


"""
Exponential moving average
"""


class EMA(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int, field: TickerFields):
        super(EMA, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.price_queue = deque(maxlen=window_size + 1)
        self.field = field
        self.ema = None
        self.multiplier = 2 / (1 + window_size)
        self.operator_name = "EMA(" + str(window_size) + ")" + " of " + ticker_name

    def get(self):
        current_price = self.exchange.fetch_ticker(self.ticker_name)[self.field]
        return self.__get_feed(current_price)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.ema
        self.price_queue.append(value)
        if len(self.price_queue) < self.window_size:
            return self.ema
        elif len(self.price_queue) == self.window_size:
            self.ema = sum(self.price_queue) / self.window_size
        else:
            self.ema += (value - self.price_queue.popleft()) * self.multiplier
        self.last_timestamp = self.exchange.__time
        return self.ema


"""
Simple moving average
"""


class SMA(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int, field: TickerFields):
        super(SMA, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.price_queue = deque(maxlen=window_size + 1)
        self.field = field
        self.sma = None
        self.operator_name = "SMA(" + str(window_size) + ")" + " of " + ticker_name

    def get(self):
        current_price = self.exchange.fetch_ticker(self.ticker_name)[self.field]
        return self.__get_feed(current_price)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.sma
        self.price_queue.append(value)
        if len(self.price_queue) < self.window_size:
            return self.sma
        elif len(self.price_queue) == self.window_size:
            self.sma = sum(self.price_queue) / self.window_size
        else:
            self.sma += (value - self.price_queue.popleft()) / self.window_size
        self.last_timestamp = self.exchange.__time
        return self.sma

    def get_feed_extern(self, value):
        return self.__get_feed(value)


"""
SMMA, the smoothed moving average
This indicator is used to facilitate standard RSI calculations.
"""


class SMMA(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int, field: TickerFields):
        super(SMMA, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.field = field
        self.smma = None
        self.operator_name = "SMMA(" + str(window_size) + ")" + " of " + ticker_name

    def get(self):
        current_price = self.exchange.fetch_ticker(self.ticker_name)[self.field]
        return self.__get_feed(current_price)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.smma
        if self.smma is None:
            self.smma = value
        else:
            self.smma = (self.smma * (self.window_size - 1) + value) / self.window_size
        self.last_timestamp = self.exchange.__time
        return self.smma

    """
    expose __get_feed to external use by choice
    """

    def get_feed_extern(self, value):
        return self.__get_feed(value)


"""
Standard Deviation indicator
this class calculates the standard deviation
of a commodity
"""


class Sigma(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int, field: TickerFields):
        super(Sigma, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.price_queue = deque(maxlen=window_size + 1)
        self.price_queue_sq = deque(maxlen=window_size + 1)
        self.price_sum = None
        self.price_sum_sq = None
        self.field = field
        self.sigma = None
        self.operator_name = "Sigma(" + str(window_size) + ")" + " of " + ticker_name

    def get(self):
        current_price = self.exchange.fetch_ticker(self.ticker_name)[self.field]
        return self.__get_feed(current_price)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.sigma
        self.last_timestamp = self.exchange.__time
        self.price_queue.append(value)
        self.price_queue_sq.append(value ** 2)
        if len(self.price_queue) != len(self.price_queue_sq):
            print("internal error: price_queue and price_queue_sq must have the same length")
            return self.sigma
        if len(self.price_queue) < self.window_size:
            return self.sigma
        elif len(self.price_queue) == self.window_size:
            self.price_sum = sum(self.price_queue)
            self.price_sum_sq = sum(self.price_queue_sq)
        else:
            self.price_sum += (value - self.price_queue.popleft())
            self.price_sum_sq += (value ** 2 - self.price_queue_sq.popleft())

        self.sigma = math.sqrt((self.price_sum_sq - self.price_sum ** 2) / (self.window_size - 1))
        return self.sigma

    def get_feed_extern(self, value):
        return self.__get_feed(value)


"""
MACD is an indicator of indicators (EMA)
"""


class MACD(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, field: TickerFields):
        super(MACD, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.ema_26 = EMA(exchange, ticker_name, 26, field)
        self.ema_12 = EMA(exchange, ticker_name, 12, field)
        self.macd = None
        self.operator_name = "SMA" + " of " + ticker_name

    def get(self):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.macd
        ema_12 = self.ema_12.get()
        ema_26 = self.ema_26.get()
        if ema_12 is None or ema_26 is None:
            self.macd = None
        else:
            self.macd = ema_12 - ema_26
        self.last_timestamp = self.exchange.__time
        return self.macd


"""
Stochastic Oscillator
it returns both %K and %D, while oscillator is commonly
used to check if %K crossed %D
"""


class StochasticOscillator(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str):
        super(StochasticOscillator, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.low_14 = None
        self.high_14 = None
        self.price_queue = deque(maxlen=14)
        self.percent_k = None
        self.past_oscillator = deque(maxlen=3)
        self.percent_d = None
        self.operator_name = "StochasticOscillator" + " of " + ticker_name

    def get(self):
        current_close = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Close]
        return self.__get_feed(current_close)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.percent_k, self.percent_d

        if len(self.price_queue) < 14:
            self.price_queue.append(value)
        else:
            self.low_14 = min(self.price_queue)
            self.high_14 = max(self.price_queue)
            self.price_queue.append(value)
            self.stochastic_oscillator = round((value - self.low_14) / (self.high_14 - self.low_14) * 100, 2)
            self.past_oscillator.append(self.stochastic_oscillator)
            self.last_timestamp = self.exchange.__time
            if len(self.past_oscillator) == 3:
                self.percent_d = round(sum(self.past_oscillator) / 3, 2)
        self.last_timestamp = self.exchange.__time
        return self.percent_k, self.percent_d


"""
RSI Index
it returns the RSI index calculated with smoothed SMA for ups and downs.
it is also an indicator of indicators
"""


class RSI(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int = 14):
        super(RSI, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.smma_up = SMMA(exchange, ticker_name, window_size, TickerFields.Close)
        self.smma_down = SMMA(exchange, ticker_name, window_size, TickerFields.Close)
        self.rsi = None
        self.close_prev = None
        self.operator_name = "RSI(" + str(self.window_size) + ")" + " of " + ticker_name

    def get(self):
        current_close = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Close]
        return self.__get_feed(current_close)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.rsi
        self.last_timestamp = self.exchange.__time
        if self.close_prev is None:
            return self.rsi
        up_price = max(0, value - self.close_prev)
        down_price = max(0, self.close_prev - value)
        smma_u = self.smma_up.get_feed_extern(up_price)
        smma_d = self.smma_down.get_feed_extern(down_price)
        if smma_u is None or smma_d is None:
            return self.rsi
        self.rsi = 100 - 100 / (1 + smma_u / smma_d)
        return self.rsi


"""
Commodity Channel Index
it returns the CCI index calculated with SMA and typical prices
see https://en.wikipedia.org/wiki/Commodity_channel_index
it is also an indicator of indicators
It uses standard deviation.
"""


class CCI(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int = 20):
        super(CCI, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        # store price as a list
        self.sigma = Sigma(exchange, ticker_name, window_size, TickerFields.Close)
        self.sma = SMA(exchange, ticker_name, window_size, TickerFields.Close)
        self.cci = None
        self.operator_name = "CCI(" + str(self.window_size) + ")" + " of " + ticker_name

    def get(self):
        current_close = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Close]
        current_high = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.High]
        current_low = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Low]
        typical_price = (current_close + current_high + current_low) / 3
        return self.__get_feed(typical_price)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.cci
        self.last_timestamp = self.exchange.__time
        sma = self.sma.get_feed_extern(value)
        sigma = self.sigma.get_feed_extern(value)
        if sma is None or sigma is None:
            return self.cci
        self.cci = (value - sma) / (0.015 * sigma)
        return self.cci


"""
Average True Range
it returns the ATR indicator
see https://en.wikipedia.org/wiki/Average_true_range
"""


class ATR(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int = 14):
        super(ATR, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        self.previous_close = None
        # store price as a list
        self.tr_queue = deque(maxlen=window_size + 1)
        self.atr = None
        self.operator_name = "ATR(" + str(self.window_size) + ")" + " of " + ticker_name

    def get(self):
        current_close = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Close]
        if self.previous_close is None:
            self.previous_close = current_close
            return None
        current_high = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.High]
        current_low = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Low]
        true_range = max(math.fabs(current_high - current_low),
                         math.fabs(current_high - self.previous_close),
                         math.fabs(self.previous_close - current_low))
        return self.__get_feed(true_range)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.atr
        self.last_timestamp = self.exchange.__time
        self.tr_queue.append(value)
        if len(self.tr_queue) < self.window_size:
            return self.atr
        elif len(self.tr_queue) == self.window_size:
            self.atr = sum(self.tr_queue) / self.window_size
        else:
            self.atr = (self.atr * (self.window_size - 1) + value) / self.window_size
        return self.atr


"""
Bollinger Bands
it returns the BB indicator calculated with SMA and standard deviations
see https://en.wikipedia.org/wiki/Bollinger_Bands
It is also an indicator of indicators
It returns a triplet of (middle_band, upper_band, lower_band)
"""


class BollingerBands(OperatorsBase):
    def __init__(self, exchange: BackExchange, ticker_name: str, window_size: int = 20):
        super(BollingerBands, self).__init__(exchange)
        self.ticker_name = ticker_name
        self.window_size = window_size
        # store price as a list
        self.sigma = Sigma(exchange, ticker_name, window_size, TickerFields.Close)
        self.sma = SMA(exchange, ticker_name, window_size, TickerFields.Close)
        self.upper_band = None
        self.lower_band = None
        self.middle_band = None
        self.operator_name = "BollingerBands(" + str(self.window_size) + ")" + " of " + ticker_name

    def get(self):
        current_close = self.exchange.fetch_ticker(self.ticker_name)[TickerFields.Close]
        return self.__get_feed(current_close)

    def __get_feed(self, value):
        if self.last_timestamp == self.exchange.__time:
            print("You attempt to calculate {} twice at ts={}".format(self.operator_name, self.last_timestamp))
            print("Please save it to a local variable and reuse it elsewhere, now using calculated value.")
            return self.middle_band, self.upper_band, self.lower_band
        self.last_timestamp = self.exchange.__time
        sma = self.sma.get_feed_extern(value)
        sigma = self.sigma.get_feed_extern(value)
        if sma is None or sigma is None:
            return self.middle_band, self.upper_band, self.lower_band
        self.middle_band, self.upper_band, self.lower_band = sma, sma + 2 * sigma, sma - 2 * sigma
        return self.middle_band, self.upper_band, self.lower_band
