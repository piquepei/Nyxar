##############
# For reference, here is the structure of order returned by ccxt library:
#
#{
#    'id':        '12345-67890:09876/54321', // string
#    'datetime':  '2017-08-17 12:42:48.000', // ISO8601 datetime with milliseconds
#    'timestamp':  1502962946216, // Unix timestamp in milliseconds
#    'status':    'open',         // 'open', 'closed', 'canceled'
#    'symbol':    'ETH/BTC',      // symbol
#    'type':      'limit',        // 'market', 'limit'
#    'side':      'buy',          // 'buy', 'sell'
#    'price':      0.06917684,    // float price in quote currency
#    'amount':     1.5,           // ordered amount of base currency
#    'filled':     1.0,           // filled amount of base currency
#    'remaining':  0.5,           // remaining amount to fill
#    'trades':   [ ... ],         // a list of order trades/executions
#    'fee':      {                // fee info, if available
#        'currency': 'BTC',       // which currency the fee is (usually quote)
#        'cost': 0.0009,          // the fee amount in that currency
#    },
#    'info':     { ... },         // the original unparsed order structure as is
#}
#
# Regarding our implementation of order class:
#
#	1. Any particular reason why timestamp should be string? Just use an integer.
#	2. I suggest create a dict for all supported currencies and an corresponding ID. Just use currency
#      name as ID.
#      Instead of saving Order.name, we should save Order.quote_currency and Order.base_currency as ID, 
#      and save Order.side as 'buy' or 'sell'. This will allow easy searching. 
#      We can of course provide a method converting these ID to pair name like "ETH/BTC". 
#   3. Should add an ID for each order, enabling the TradeAlgo to query and cancel that order. 
#   4. Instead of saving Order.fill_percentage, save Order.filled. Percentage and remaining should be 
#      calculated through provided method. 
#   5. The balance of each currency can be a list, accessed by currency ID. Lets make Currency String Name
#      as its ID.
#   
# Regarding our general implementation:
#   1. We don't need to distinguish open order and order. All orders should have filled amount. 
#      (See History order in binance)
#   2. We also need to create a trade class, and store all past trades. See "trades" in the previous structure,
#      and the following 
#   3. Here is what happens in every time cycle: 
#	   Note that the order placed on this timestamp will always be processed at next timestamp.
#       a. Update the latest market price based on timestamp. 
#       b. Resolve all open orders in OpenOrder. 
#          1) For limit order, check if the current price meets the fill condition. 
#		   2) Set the price to be this timestamps close price, for fulfilled limit order or market order.
#			  (This part should be tunable. As one may also want to use high price for buy and low price 
#			   for sell in order to get more realistic results. )
#		   3) Call predefined slippage model to determine how the orders are filled (volume, fee, etc). 
#		   4) Create corresponding trades and store in history trades. 
#		   5) Update Order.filled and append Order.trades. Both OpenOrder and HistoryOrder should be updated 
#			  automatically, as only the reference is saved. 
#		   6) Update account balance. 
#       c. Accepet requests from TradeAlgo, including
#		   1) Place/cancel/query order (through order ID). 
#          2) Query account balance.
#		   3) Query market. (Not sure if we just automatically send the latest market data to TradeAlgo. )
#          4) Query history trades or orderbook. 
#		d. Before placing an order, first check if the account balance is enough. 
#          As long as an order is placed, we create a new Order object, and put its reference in both 
#          HistoryOrder and OpenOrder. 
#
# More on Slippage model:
#   Exchange should be able to accept (optional) bid/ask. The slippage model should be able to run based
#   on it. I think slippage is particularly important in cryptocurrency, due to the lack of liquidity and
#   large bid-ask spread for altcoins. 
#   
#   Here is the API for slippage model in Zipline:
#   ``Your custom model must be a class that inherits from slippage.SlippageModel and implements 
#     process_order(self, data, order). The process_order method must return a tuple of 
#     (execution_price, execution_volume), which signifies the price and volume for the transaction that 
#     your model wants to generate. The transaction is then created for you. ''
#
# More features to add:
#   1. Stop-loss/Stop-limit order. It is important because the order is placed and executed at different time. 
#   2. More slippage model.
#
#
#############

from backtest.errors import InvalidOrder, OrderNotFound

from enum import Enum
from datetime import datetime
from collections import OrderedDict

class OrderSide(Enum):
    Buy = "buy"
    Sell = "sell"


class OrderType(Enum):
    Limit = "limit"
    Market = "market"


class OrderStatus(Enum):
    Submitted = "submitted"
    Open = "open"
    Filled = "filled"
    Cancelled = "cancelled"


class Transaction(object):
    def __init__(self, *, quote_name: str, base_name: str, price: float, amount: float, side: OrderSide,
                 timestamp: int):
        self.timestamp = timestamp
        self.datetime = datetime.fromtimestamp(timestamp / 1000.0)
        self.side = side
        self.quote_name = quote_name
        self.base_name = base_name
        self.symbol = quote_name + "/" + base_name
        self.amount = amount
        self.price = price
        self.id = self.get_unique_id()

    def get_unique_id(self) -> str:
        # should be unique, datetime + name
        return self.get_datetime().isoformat() + ':' + self.symbol

    def get_datetime(self) -> datetime:
        return self.datetime

    def get_id(self) -> str:
        return self.id

    def __repr__(self):
        return 'Timestamp: ' + str(self.timestamp) + ' ' + self.side.value + ' ' + str(self.amount) + ' ' + \
               self.quote_name + ' at price ' + str(self.price) + ' per ' + self.base_name


class Order(object):
    def __init__(self, quote_name: str, base_name: str, price: float, amount: float, order_type: OrderType,
                 side: OrderSide, timestamp: int):
        assert isinstance(order_type, OrderType), "type must be OrderType"
        assert isinstance(side, OrderSide), "status must be OrderStatus"
        assert isinstance(quote_name, str), "quote_name must be string"
        assert isinstance(base_name, str), "base_name must be string"
        assert isinstance(timestamp, int), "timestamp must be integer"
        assert isinstance(amount, int), "amount must be integer"
        assert amount >= 0, "size must be a positive number"
        if order_type == OrderType.Limit:
            assert price >= 0, "price must be a positive number"

        self.timestamp = timestamp
        self.datetime = datetime.fromtimestamp(timestamp/1000.0)  # datatime object
        self.status = OrderStatus.Submitted
        self.type = order_type
        self.side = side
        self.quote_name = quote_name
        self.base_name = base_name
        self.symbol = quote_name + "/" + base_name
        self.amount = amount
        self.price = price
        self.filled = 0
        self.transactions = []
        self.fee = {}
        self.id = self.get_unique_id()

    def get_unique_id(self) -> str:
        # should be unique, datetime + name
        return self.get_datetime().isoformat() + ':' + self.symbol

    def get_datetime(self) -> datetime:
        return self.datetime

    def get_id(self) -> str:
        return self.id

    def get_price(self) -> float:
        return self.price

    def get_amount(self) -> float:
        return self.amount

    def get_remaining(self) -> float:
        return self.amount - self.filled

    def get_type(self) -> OrderType:
        return self.type

    def get_status(self) -> OrderStatus:
        return self.status

    def get_timestamp(self) -> int:
        return self.timestamp

    def get_side(self) -> OrderSide:
        return self.side

    def get_filled_percentage(self) -> float:
        return 1.0 * self.filled / self.amount

    def get_transactions(self):
        return self.transactions

    def get_base_name(self):
        return self.base_name

    def get_quote_name(self):
        return self.quote_name

    def get_symbol(self):
        return self.symbol

    def get_info(self):
        return {'id': self.id, 'datetime': str(self.datetime), 'timestamp': self.timestamp, 'status': self.status,
                'symbol': self.symbol, 'type': self.type.value, 'side': self.side.value, 'price': self.price,
                'amount': self.amount, 'filled': self.filled, 'remaining': self.get_remaining(),
                'transaction': self.transactions, 'fee': self.fee}

    def cancel(self):
        self.status = OrderStatus.Cancelled

    def open(self):
        assert self.type is not OrderType.Market
        self.status = OrderStatus.Open

    def generate_transaction(self, *, amount: float, price: float, timestamp: int) -> Transaction:
        return Transaction(quote_name=self.quote_name,
                           base_name=self.base_name,
                           price=price,
                           amount=amount,
                           side=self.side,
                           timestamp=timestamp)

    def execute_transaction(self, transaction: Transaction) -> bool:
        """
        Returns:
             A bool indicates whether the order is filled or not.
        """
        assert isinstance(transaction, Transaction), "type must be transaction"

        if transaction.side == OrderSide.Buy:
            self.filled += transaction.amount
            self.transactions.append(transaction)
        else:
            self.filled += transaction.amount
            self.transactions.append(transaction)

        assert self.amount - self.filled >= 0

        if self.amount - self.filled == 0:
            self.status = OrderStatus.Filled
            return True
        else:
            return False

    def pay_fee(self, asset: str, amount: float):
        if asset not in self.fee:
            self.fee[asset] = amount
        else:
            self.fee[asset] += amount


class OrderBook(object):
    def __init__(self):
        self.book = {}

    def add_new_order(self, quote_name, base_name, price, amount, order_type, side, timestamp):
        new_order = Order(quote_name, base_name, price, amount, order_type, side, timestamp)
        self.book[new_order.get_id()] = new_order
        return new_order.get_id()

    def insert_order(self, order: Order):
        self.book[order.get_id()] = order

    def remove_order(self, order: Order):
        if order.get_id() in self.book:
            del self.book[order.get_id()]
        else:
            raise OrderNotFound

    def get_order(self, order_id: str) -> Order:
        if order_id in self.book:
            return self.book[order_id]
        else:
            raise OrderNotFound

    def is_empty(self):
        return len(self.book) == 0

    def get_all_order_id(self) -> set:
        return set(self.book.keys())

    def __iter__(self):
        return iter(self.book.values())


class OrderQueue(OrderBook):
    def __init__(self):
        self.book = OrderedDict()

    def pop_order(self) -> Order:
        return self.book.popitem(last=False)[1]