import calendar
import datetime
import hashlib
import hmac
import logging
import math
from urllib.parse import quote_plus
import urllib3
from json import loads, dumps
from bots.settings import *
import requests
from math import floor
import pandas as pd
from time import sleep
import time
import numpy as np

log_debug = logging.getLogger('bots_debug')
log_info = logging.getLogger('bots_info')
log_error = logging.getLogger('bots_error')

file_handler_debug = logging.FileHandler(filename='logs/bots.log')
file_handler_debug.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_debug.setLevel(logging.DEBUG)
log_debug.addHandler(file_handler_debug)
log_debug.setLevel(logging.DEBUG)

file_handler_info = logging.FileHandler(filename='logs/bots.log')
file_handler_info.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_info.setLevel(logging.INFO)
log_info.addHandler(file_handler_info)
log_info.setLevel(logging.INFO)

file_handler_error = logging.FileHandler(filename='logs/bots.log')
file_handler_error.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_error.setLevel(logging.ERROR)
log_error.addHandler(file_handler_error)
log_error.setLevel(logging.ERROR)


class BotBybit:

    def __init__(self, api_key: str, api_secret: str):
        """
        Initializing the parent bot
        :param api_key: api account key
        :type api_key: str
        :param api_secret: api account secret key
        :type api_secret: str
        :return: None
        """
        self.api_key = api_key
        self.api_secret = api_secret

    def go_command(self, method: str, url: str, secret_key: str, params: dict, proxies: dict):
        """
        Function creating a request
        :param method: GET or POST
        :type method: str
        :param url: url bybit
        :type url: str
        :param secret_key: client's secret key
        :type secret_key: str
        :param params: dict with data for request
        :type params: str
        :param proxies: dict with proxy
        :type proxies: dict
        :return: dict with data
        """

        # Create the param str
        param_str = ""
        for key in sorted(params.keys()):
            v = params[key]
            if isinstance(params[key], bool):
                if params[key]:
                    v = "true"
                else:
                    v = "false"
            param_str += f"{key}={v}&"
        param_str = param_str[:-1]

        # Generate the signature
        hash = hmac.new(bytes(secret_key, "utf-8"), param_str.encode("utf-8"),
                        hashlib.sha256)
        signature = hash.hexdigest()
        sign_real = {
            "sign": signature
        }
        # Prepare params in the query string format
        # quote_plus helps quote rare characters like "/" and "+"; this must be
        # applied after the signature generation.
        param_str = quote_plus(param_str, safe="=&")
        full_param_str = f"{param_str}&sign={sign_real['sign']}"
        # Request information
        if "spot" in url or method == "GET":
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            body = None
        else:
            headers = {"Content-Type": "application/json"}
            body = dict(params, **sign_real)

        urllib3.disable_warnings()
        s = requests.session()
        s.keep_alive = False

        # Send the request(s)

        if "spot" in url:
            # Send a request to the spot API
            response = requests.request(method, f"{url}?{full_param_str}",
                                        headers=headers, verify=False)
        else:
            # Send a request to the futures API
            if method == "POST":
                response = requests.request(method, url, data=dumps(body),
                                            headers=headers, verify=False, proxies=proxies)
            else:  # GET
                response = requests.request(method, f"{url}?{full_param_str}",
                                            headers=headers, verify=False, proxies=proxies)

        return loads(response.text)

    def get_timestamp(self, proxy):
        """
        Get timestamp function
        :return: time
        """
        resp = requests.request('GET', url='https://api-testnet.bybit.com/v2/public/time', proxies={'http': proxy})
        server_time = int(float(loads(resp.text)['time_now']) * 1000)
        return server_time


class BotTrader(BotBybit):

    def __init__(self, api_key: str, api_secret: str, symbol: str, proxy: str, interval: int):
        """
        Initializing the parent bot
        :param api_key: api account key
        :type api_key: str
        :param api_secret: api account secret key
        :type api_secret: str
        :param symbol: symbol instrument
        :type symbol: str
        :param proxy: proxy
        :type proxy: str
        :param interval: interval trading (minutes)
        :type proxy: int
        :return: None
        """
        super().__init__(api_key, api_secret)
        self.symbol = symbol
        self.proxy = proxy
        self.qty_market = 0
        self.list_order_limit_by_del = []
        self.interval = interval

    def _log_information(self, **kwargs):
        """
        Logging and outputting information about the order to the console
        :param kwargs: dict parameters
        :type kwargs: dict
        :return: None
        """
        try:
            log_info.info(
                msg=MESSAGE_LOG.format(kwargs['symbol'], kwargs['side'], kwargs['order_type'],
                                       kwargs['price'],
                                       kwargs['qty']))
        except Exception as exc:
            log_error.error(exc)

    def get_params(self):
        """
        :return: dict of params:
            -balance
            -currency
            -balance in usd
        """
        method = 'GET'
        url = 'https://api-testnet.bybit.com/v2/private/wallet/balance'
        data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(proxy=self.proxy)}
        try:
            response_balance = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        except  Exception as exc:
            log_error.error(exc)
            return None
        try:
            self.balance = response_balance['result']['USDT']['available_balance']
        except Exception as exc:
            log_error.error(exc)
            return None
        now = datetime.datetime.utcnow()
        unixtime = calendar.timegm(now.utctimetuple())
        since = unixtime - self.interval * 60 * 200
        method = 'GET'
        url = f'https://api-testnet.bybit.com/public/linear/kline?symbol={self.symbol}&interval={self.interval}&from={since}'
        response_currency = loads(requests.request(method, url, verify=False, proxies={'http': self.proxy}).text)
        currency = response_currency['result'][-1]['close']
        data_dict = {
            'balance': self.balance,
            'currency': currency
        }
        return data_dict
    
    def calculate_limit_price(self, direction):
        limit_price = None
        while limit_price is None:
            try:
                last_price = float(self.get_params()['currency'])
                if direction == 'long':
                    limit_price = last_price - 2
                else:
                    limit_price = last_price + 2
            except Exception as exc:
                log_error.error(exc)
                time.sleep(0.1)
        return limit_price

    def find_price(self):
        return float(self.get_params()['currency'])

    def calculate_qty(self, percent: float):
        """
        Function calculating qty
        :param percent: percent
        :type percent: float
        :return: qty for limit
        """
        param_dict = self.get_params()
        if param_dict is None:
            return 0
        percents_from_balance = self.percentator(param_dict['balance'], percent)
        percents_from_balance *= 100
        value = self.usdt_to_btc(percents_from_balance, param_dict['currency'])
        self.qty_market = self.my_round(value)
        return self.qty_market

    def post_market_order(self, direction: str, percent: float):
        """
        Function post market order
        :param direction: long or short
        :type direction: str
        :param percent: percent
        :type percent: float
        :return: None
        """
        try:
            self.calculate_qty(percent=percent)
        except Exception as exc:
            log_error.error(exc)
            self.qty_market = 0
        try:
            method = "POST"
            url = "https://api-testnet.bybit.com/private/linear/order/create"
            if direction == 'long':
                data = {"api_key": self.api_key, "side": "Buy", "symbol": self.symbol,
                        "order_type": "Market", "qty": self.qty_market,
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": False, "close_on_trigger": False}
                response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
                result = response['result']
                information_log = dict(symbol=result['symbol'], side='Buy', order_type=result['order_type'],
                                       price=result['price'],
                                       qty=result['qty'])
            else:
                data = {"api_key": self.api_key, "side": "Sell", "symbol": self.symbol,
                        "order_type": "Market", "qty": self.qty_market,
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": False, "close_on_trigger": False}
                response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
                result = response['result']
                information_log = dict(symbol=result['symbol'], side='Sell', order_type=result['order_type'],
                                       price=result['price'],
                                       qty=result['qty'])
            self._log_information(**information_log)
        except Exception as exc:
            log_error.error(exc)

    def round_limit_orders(self, qty: float):
        """
        Function round limit orders
        :param qty: qty
        :type qty: float
        :return: round qty
        :rtype: float
        """
        limit = int(qty * 1000)
        limit /= 1000
        return limit

    def get_order_id(self, direction: str):
        """
        Function found open order id
        :param direction: long or short
        :type direction: str
        :return: order_id
        :rtype: str
        """
        url = 'https://api-testnet.bybit.com/private/linear/trade/execution/list'
        method = 'GET'
        data = {"api_key": self.api_key, "symbol": self.symbol,
                "timestamp": self.get_timestamp(proxy={'http': f'http://{self.proxy}'}),
                'limit': 200}

        response_history = self.go_command(method, url, self.api_secret, data, {'http': f'http://{self.proxy}'})
        for info in response_history['result']['data']:
            if direction == 'long':
                if info['side'] == 'Buy' and float(info['closed_size']) == float(0):
                    return info['order_id']
            else:
                if info['side'] == 'Sell' and float(info['closed_size']) == float(0):
                    return info['order_id']

    def post_limit_order(self, percent_limit: float, limit_price: float, direction: str,
                         reduce_only: bool):
        """
        Function post limit orders
        :param percent_limit: percent fo limit order
        :rtype percent_limit: float
        :param limit_price: price for limit
        :rtype limit_price: float
        :param direction: long or short
        :rtype direction: str
        :param slider: value from the slider?
        :type slider: bool
        :param reduce_only: open or close order (True or False)
        :type reduce_only: bool
        :return: None
        """
        try:
            if reduce_only is False:
                try:
                    qty_limit = self.calculate_qty(percent_limit)
                except Exception as exc:
                    log_error.error(exc)
                    qty_limit = 0
            else:
                try:
                    qty_market = self.get_market_qty(direction, reduce_only)
                    qty_limit = float(qty_market * percent_limit / 100)
                    qty_limit = self.round_limit_orders(qty_limit)
                except Exception as exc:
                    log_error.error(exc)
                    qty_limit = 0
            method = "POST"
            url = "https://api-testnet.bybit.com/private/linear/order/create"
            if direction == 'long':
                data = {"api_key": self.api_key, "side": "Buy", "symbol": self.symbol,
                        "order_type": "Limit", "qty": qty_limit, 'price': limit_price,
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": reduce_only, "close_on_trigger": False}
                response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
                result = response['result']
                information_log = dict(symbol=result['symbol'], side='Buy', order_type=result['order_type'],
                                       price=result['price'],
                                       qty=result['qty'])
                return result['qty']
            else:
                data = {"api_key": self.api_key, "side": "Sell", "symbol": self.symbol,
                        "order_type": "Limit", "qty": qty_limit, 'price': limit_price,
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": reduce_only, "close_on_trigger": False}
                response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
                result = response['result']
                information_log = dict(symbol=result['symbol'], side='Sell', order_type=result['order_type'],
                                       price=result['price'],
                                       qty=result['qty'])
                return result['qty']
            self._log_information(**information_log)
        except Exception as exc:
            log_error.error(exc)

    def del_limit_order(self, direction: str, reduce_only: bool, list_orders=None):
        """
        Function del limit orders
        :param direction: long or short
        :type direction: str
        :param reduce_only: True or False (open or close limite order)
        :type direction: bool
        :return: None
        """
        method = "POST"
        url = "https://api-testnet.bybit.com/private/linear/order/cancel"
        if list_orders is not None:
            for order_id in list_orders:
                data = {"api_key": self.api_key, "symbol": self.symbol,
                        "order_id": order_id, "timestamp": self.get_timestamp(self.proxy)}
                resp = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        else:
            self.get_limit_orders_by_del(direction, reduce_only)
            try:
                if self.list_order_limit_by_del is None:
                    return
                for order_id in self.list_order_limit_by_del:
                    data = {"api_key": self.api_key, "symbol": self.symbol,
                            "order_id": order_id, "timestamp": self.get_timestamp(self.proxy)}

                    resp = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
            except Exception as exc:
                log_error.error(exc)

    def get_info_open_limit_orders(self, direction: str, reduce_only: bool):
        method = 'GET'
        url = 'https://api-testnet.bybit.com/private/linear/order/search'
        data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
        response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        try:
            list_order_limit = [(dict_info['order_id'], dict_info['price'])  for dict_info in response['result'] if
                                     dict_info['side'] == direction and dict_info['reduce_only'] == reduce_only]
            return list_order_limit
        except Exception as exc:
            log_error.error(exc)
            return None


    def get_limit_orders_by_del(self, direction: str, reduce_only: bool):
        """
        Function get information about limit orders
        :param direction: long or short
        :type direction: str
        :return: None
        """
        method = 'GET'
        url = 'https://api-testnet.bybit.com/private/linear/order/search'
        data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
        response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        try:
            self.list_order_limit_by_del = [dict_info['order_id'] for dict_info in response['result'] if
                                     dict_info['side'] == direction and dict_info['reduce_only'] == reduce_only]
        except Exception as exc:
            log_error.error(exc)
            return None

    def put_stop_loss(self, stop_loss: int, side: str):
        """
        Function put stop loss
        :param stop_loss: value stop loss
        :type stop_loss: int
        :param side: long or short
        :type side: str
        :return: None
        """
        try:
            method = "POST"
            url = "https://api-testnet.bybit.com/private/linear/position/trading-stop"
            data = {"api_key": self.api_key, "symbol": self.symbol, 'side': side,
                    "stop_loss": stop_loss, "timestamp": self.get_timestamp(self.proxy)}
            self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        except Exception as exc:
            log_error.error(exc)

    def get_market_qty(self, direction: str, reduce_only: bool):
        """
        Function getting market qty
        :param direction: long or short
        :type direction: str
        :return: qty market position
        :rtype: float
        """
        method = 'GET'
        url = 'https://api-testnet.bybit.com/private/linear/position/list'
        data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
        response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        if direction == 'long' and reduce_only is True: 
            return float(response['result'][1]['size'])
        elif direction == 'short' and reduce_only is True:
            return float(response['result'][0]['size'])
        elif direction == 'long' and reduce_only is False:
            return float(response['result'][0]['size'])
        else:
            return float(response['result'][1]['size'])

    def get_market_entry_price(self, direction: str):
        checking = None
        while checking is None:
            try:
                method = 'GET'
                url = 'https://api-testnet.bybit.com/private/linear/position/list'
                data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
                response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
                if direction == 'long':
                    return float(response['result'][0]['entry_price'])
                else:
                    return float(response['result'][1]['entry_price'])
            except Exception as exc:
                time.sleep(0.1)
                log_error.error(exc)

    def market_all(self, side: str):
        """
        Function close position orders
        :param side: Buy or Sell
        :type side: str
        :return: None
        """
        try:
            method = 'GET'
            url = 'https://api-testnet.bybit.com/private/linear/position/list'
            data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
            response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
            url = "https://api-testnet.bybit.com/private/linear/order/create"
            method = 'POST'
            if side == 'Buy':
                order_id_link = self.get_order_id('long')
                data = {"api_key": self.api_key, "side": "Sell", "symbol": self.symbol,
                        "order_type": "Market", "qty": float(response['result'][0]['size']),
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": True, "close_on_trigger": False, 'order_link_id': order_id_link}
                self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
            else:
                order_id_link = self.get_order_id('short')
                data = {"api_key": self.api_key, "side": "Buy", "symbol": self.symbol,
                        "order_type": "Market", "qty": float(response['result'][1]['size']),
                        "time_in_force": "GoodTillCancel", "timestamp": self.get_timestamp(self.proxy),
                        "reduce_only": True, "close_on_trigger": False, 'order_link_id': order_id_link}
                self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        except Exception as exc:
            log_error.error(exc)

    def usdt_to_btc(self, usdt: float, currency: float):
        """
        Transfer usdt to btc
        :param usdt: usdt value
        :type usdt: float
        :param currency: currency
        :type currency: float
        :return: btc value
        :rtype: float
        """
        btc = usdt / float(currency)
        return btc


    def percentator(self, percent, value):
        """
        :param percent: percent as int
        :param value: target value
        :return: n percent of value
        """
        percent = percent / 100
        return value * percent


    def my_round(self, value):
        """
        Funсtion round value
        :param value: value
        :type value: float
        :return: value
        :rtype: float
        """
        dif = value * 1000
        dif = math.floor(dif)
        true_value = dif / 1000
        return true_value

    def get_qty_limits_order(self, side):
        """
        Function get information about limit orders
        :param direction: long or short
        :type direction: str
        :return: None
        """
        method = 'GET'
        url = 'https://api-testnet.bybit.com/private/linear/order/search'
        data = {"api_key": self.api_key, "symbol": self.symbol, "timestamp": self.get_timestamp(self.proxy)}
        response = self.go_command(method, url, self.api_secret, data, {'http': self.proxy})
        try:
            list_order_limit = [dict_info['order_id'] for dict_info in response['result'] if
                                     dict_info['side'] == side and dict_info['reduce_only'] == False]
            count_limit_orders = len(list_order_limit)
            return count_limit_orders
        except Exception as exc:
            log_error.error(exc)
            return None

class FlatBotTrader(BotTrader):

    def __init__(self, api_key: str, api_secret: str, symbol: str, proxy: str, interval: int, limits_threshold: list):
        """
        Initializing the parent bot
        :param api_key: api account key
        :type api_key: str
        :param api_secret: api account secret key
        :type api_secret: str
        :param symbol: symbol instrument
        :type symbol: str
        :param proxy: proxy
        :type proxy: str
        :return: None
        """
        super().__init__(api_key, api_secret, symbol, proxy, interval)
        self.interval
        self.limits_threshold =  limits_threshold


    def work_short(self):
        log_info.info("bot started working in short!!!")
        while True:
            self.stop_price_short = 0
            try:
                limit_price = self.calculate_limit_price('short')
                limit_qty = self.post_limit_order(percent_limit=1, limit_price=limit_price, direction='short',
                                     reduce_only=False)
                market_qty = self.get_market_qty(direction='short', reduce_only = False)
                while market_qty == 0:
                    try:
                        dif = limit_price - self.find_price()
                        if dif > 5:
                            self.del_limit_order('Sell', reduce_only=False)
                            limit_price = self.calculate_limit_price('short')
                            limit_qty = self.post_limit_order(percent_limit=1, limit_price=limit_price,
                                                 direction='short',
                                                 reduce_only=False)
                        market_qty = self.get_market_qty(direction='short', reduce_only = False)
                        time.sleep(0.3)
                    except Exception as exc:
                        log_error.error(exc)
                        time.sleep(1)
                else:
                    log_info.info("bot entered the trade in short!!!")
                    entry_price = floor(self.get_market_entry_price('short'))
                    self.post_limit_order(percent_limit=100, limit_price=entry_price - 50,
                                         direction='long',
                                         reduce_only=True)
                    for percent, price in self.limits_threshold:
                        self.post_limit_order(percent_limit=percent, limit_price=entry_price + price,
                                             direction='short',
                                             reduce_only=False)
                        time.sleep(0.3)
                    stop_price_short = entry_price + 500 + self.limits_threshold[1][1]
                    self.put_stop_loss(stop_loss=stop_price_short, side='Sell')
                    market_qty = self.get_market_qty(direction='Sell', reduce_only = False)
                    qty_limit_orders_start = self.get_qty_limits_order('Sell')
                    log_info.info("bot arranged extras and stop losses in short!!!")
                    while market_qty != 0:
                        try:
                            time.sleep(0.5)
                            qty_limit_orders = self.get_qty_limits_order('Sell')
                            if qty_limit_orders is not None:
                                if qty_limit_orders_start > qty_limit_orders:
                                    qty_limit_orders_start = qty_limit_orders
                                    self.del_limit_order('Buy', reduce_only=True)
                                    entry_price = floor(self.get_market_entry_price('short'))
                                    self.post_limit_order(percent_limit=100,
                                                         limit_price=entry_price - 50,
                                                         direction='long',
                                                         reduce_only=True)
                                    log_info.info("bot collected an additional short!!!")
                            time.sleep(1)
                            market_qty = self.get_market_qty(direction='short', reduce_only = False)
                        except Exception as exc:
                            log_error.error(exc)
                            time.sleep(1)
                    time.sleep(1)
                    self.del_limit_order('Sell', reduce_only=False)
                    price_now = self.find_price()
                    if price_now >= self.stop_price_short - 10:
                        log_info.info("bot caught stop loss in short!!!")
                        return
                log_info.info("bot came out of short!!!")
                time.sleep(1)
            except Exception as exc:
                log_error.error(exc)

    def work_long(self):
        log_info.info("bot started working in long!!!")
        self.stop_price_long = 0
        while True:
            try:
                limit_price = self.calculate_limit_price('long')
                self.post_limit_order(percent_limit=1,
                                     limit_price=limit_price,
                                     direction='long',
                                     reduce_only=False)
                time.sleep(0.3)
                market_qty = self.get_market_qty(direction='long', reduce_only = False)
                while market_qty == 0:
                    try:
                        dif = self.find_price() - limit_price
                        if dif > 5:
                            self.del_limit_order('Buy', reduce_only=False)
                            limit_price = self.calculate_limit_price('long')
                            self.post_limit_order(percent_limit=1,
                                                 limit_price=limit_price,
                                                 direction='long',
                                                 reduce_only=False)
                        time.sleep(0.3)
                        market_qty = self.get_market_qty(direction='long', reduce_only = False)
                    except Exception as exc:
                        log_error.error(exc)
                        time.sleep(1)
                else:
                    log_info.info("bot entered the trade in long!!!")
                    entry_price = floor(self.get_market_entry_price('long'))
                    self.post_limit_order(percent_limit=100, limit_price=entry_price + 50,
                                         direction='short',
                                         reduce_only=True)
                    for percent, price in self.limits_threshold:
                        self.post_limit_order(percent_limit=percent, limit_price=entry_price - price,
                                             direction='long',
                                             reduce_only=False)
                    self.stop_price_long = entry_price - self.limits_threshold[1][1] - 500
                    self.put_stop_loss(stop_loss=self.stop_price_long, side='Buy')
                    market_qty = self.get_market_qty(direction='long', reduce_only = False)
                    qty_limit_orders_start = self.get_qty_limits_order('Buy')
                    log_info.info("bot arranged extras and stop losses in long!!!")
                    while market_qty != 0:
                        try:
                            time.sleep(0.5)
                            qty_limit_orders = self.get_qty_limits_order('Buy')
                            if qty_limit_orders is not None:
                                if qty_limit_orders_start > qty_limit_orders:
                                    qty_limit_orders_start = qty_limit_orders
                                    self.del_limit_order('Sell', reduce_only=True)
                                    entry_price = floor(self.get_market_entry_price('long'))
                                    self.post_limit_order(percent_limit=100,
                                                         limit_price=entry_price + 50,
                                                         direction='short',
                                                         reduce_only=True)
                                    log_info.info("bot collected an additional long!!!")
                            time.sleep(1)
                            market_qty = self.get_market_qty(direction='long', reduce_only = False)
                        except Exception as exc:
                            log_error.error(exc)
                            time.sleep(1)
                    time.sleep(1)
                    self.del_limit_order('Buy', reduce_only=False)
                    price_now = self.find_price()
                    if price_now <= self.stop_price_long + 10:
                        log_info.info("bot caught stop loss in long!!!")
                        return
                log_info.info("bot came out of long!!!")
                time.sleep(1)
            except Exception as exc:
                log_error.error(exc)
                time.sleep(1)