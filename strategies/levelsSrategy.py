from bots.bots import *
from configs.config import host_redis, port_redis, TAKE_PROFIT, STOP_LOSS, MAX_COUNT_LIMIT_ORDERS, DANGEROUS_AREA, SUPERIORITY, MODE
import redis
from json import loads
from math import floor
from multiprocessing import Process
import logging

REDIS_CON = redis.Redis(host=host_redis, port=port_redis, db=0)

log_debug = logging.getLogger('bots_debug')
log_info = logging.getLogger('bots_info')
log_error = logging.getLogger('bots_error')

file_handler_debug = logging.FileHandler(filename='logs/strategy_levels.log')
file_handler_debug.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_debug.setLevel(logging.DEBUG)
log_debug.addHandler(file_handler_debug)
log_debug.setLevel(logging.DEBUG)

file_handler_info = logging.FileHandler(filename='logs/strategy_levels.log')
file_handler_info.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_info.setLevel(logging.INFO)
log_info.addHandler(file_handler_info)
log_info.setLevel(logging.INFO)

file_handler_error = logging.FileHandler(filename='logs/strategy_levels.log')
file_handler_error.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%d-%m-%Y %H:%M'))
file_handler_error.setLevel(logging.ERROR)
log_error.addHandler(file_handler_error)
log_error.setLevel(logging.ERROR)

def get_support_level():
    levels = loads(REDIS_CON.get("levels"))
    last_value = REDIS_CON.get("last_value")
    support_level = [value for index, value in levels if value < float(last_value)]
    support_level.sort(reverse=True)
    return support_level

def get_resistance_level():
    levels = loads(REDIS_CON.get("levels"))
    last_value = REDIS_CON.get("last_value")
    resistance_level = [value for index, value in levels if value > float(last_value)]
    resistance_level.sort(reverse=False)
    return resistance_level

def define_level(bot_trader, direction):
    new_limit_orders_price = []
    del_limit_orders_id = []
    if direction == "Buy":
        levels = get_support_level()
    else:
        levels = get_resistance_level()
    open_limit_orders = bot_trader.get_info_open_limit_orders(direction, False)
    prices_current_limit_orders = [info[1] for info in open_limit_orders]
    count_open_limit_orders = len(open_limit_orders)
    for level in levels:
        if level not in prices_current_limit_orders:
            new_limit_orders_price.append(level)
    for iD, price, qty in open_limit_orders:
        if price not in levels:
            del_limit_orders_id.append(iD)
    if count_open_limit_orders >= 3:
        new_limit_orders_price = []
    elif count_open_limit_orders == 0 and len(new_limit_orders_price) < 2:
        new_limit_orders_price = []
    if direction == "Buy":
        new_limit_orders_price.sort(reverse=True)
    else:
        new_limit_orders_price.sort(reverse=False)
    needed_count_orders = MAX_COUNT_LIMIT_ORDERS - count_open_limit_orders
    if len(new_limit_orders_price) >= needed_count_orders:
        new_limit_orders_price = new_limit_orders_price[0:needed_count_orders]
    return new_limit_orders_price, del_limit_orders_id 

def watch_out_danger_long(bot_trader):
    while True:
        open_limit_orders = bot_trader.get_info_open_limit_orders('Buy', False)
        if len(open_limit_orders) > 0:
            open_limit_orders = sorted(open_limit_orders, key=lambda x:x[1])
            first_limit_order = open_limit_orders[-1][1]
            last_value = float(REDIS_CON.get("last_value"))
            superiority_sell = float(REDIS_CON.get("superiority_sell"))
            dif_price = last_value - first_limit_order
            if dif_price <= DANGEROUS_AREA and superiority_sell > SUPERIORITY:
                bot_trader.del_limit_order("Buy", False, [open_limit_orders[-1][0]])
                log_info.info("bot deleted long open limit order with id = " + open_limit_orders[-1][0])


def watch_out_danger_short(bot_trader):
    while True:
        open_limit_orders = bot_trader.get_info_open_limit_orders('Sell', False)
        if len(open_limit_orders) > 0:
            open_limit_orders = sorted(open_limit_orders, key=lambda x:x[1])
            first_limit_order = open_limit_orders[0][1]
            last_value = float(REDIS_CON.get("last_value"))
            superiority_buy = float(REDIS_CON.get("superiority_buy"))
            dif_price = first_limit_order - last_value
            if dif_price <= DANGEROUS_AREA and superiority_buy > SUPERIORITY:
                bot_trader.del_limit_order("Sell", False, [open_limit_orders[0][0]])
                log_info.info("bot deleted short open limit order with id = " + open_limit_orders[0][0])



def trade_long(bot_trader):
    log_info.info("bot started working in long!!!")
    while True:
        market_qty = bot_trader.get_market_qty(direction = 'long', reduce_only = False)
        while market_qty == 0:
            new_limit_orders_price, del_limit_orders_id = define_level(bot_trader, "Buy")
            for index, value in enumerate(new_limit_orders_price):
                bot_trader.post_limit_order(percent_limit = index + 1,
                                        limit_price = value,
                                        direction = 'long',
                                        reduce_only = False)
            if len(del_limit_orders_id) > 0:
                bot_trader.del_limit_order("Buy", False, del_limit_orders_id)
            market_qty = bot_trader.get_market_qty(direction = 'long', reduce_only = False)
        else:
            log_info.info("bot entered the trade in long!!!")
            entry_price = floor(bot_trader.get_market_entry_price('long'))
            take_profit_value = entry_price + TAKE_PROFIT
            bot_trader.post_limit_order(percent_limit = 100, limit_price = take_profit_value,
                                    direction = 'short',
                                    reduce_only = True)
            last_limit_order = bot_trader.get_price_last_draw_limit_order("Buy", False)
            bot_trader.stop_price_long = last_limit_order - STOP_LOSS
            bot_trader.put_stop_loss(stop_loss = bot_trader.stop_price_long, side = 'Buy')
            market_qty = bot_trader.get_market_qty(direction='long', reduce_only = False)
            qty_limit_orders_start = bot_trader.get_qty_limits_order('Buy')
            log_info.info("bot arranged extras and stop losses in long!!!")
            while market_qty != 0:
                try:
                    time.sleep(0.5)
                    qty_limit_orders = bot_trader.get_qty_limits_order('Buy')
                    if qty_limit_orders is not None:
                        if qty_limit_orders_start > qty_limit_orders:
                            qty_limit_orders_start = qty_limit_orders
                            bot_trader.del_limit_order('Sell', reduce_only = True)
                            entry_price = floor(bot_trader.get_market_entry_price('long'))
                            take_profit_value = entry_price + TAKE_PROFIT
                            bot_trader.post_limit_order(percent_limit = 100,
                                                    limit_price = take_profit_value,
                                                    direction = 'short',
                                                    reduce_only = True)
                            log_info.info("bot collected an additional long!!!")
                    time.sleep(1)
                    market_qty = bot_trader.get_market_qty(direction='long', reduce_only = False)
                    try:
                        take_qty = bot_trader.get_info_open_limit_orders(direction='Sell', reduce_only = True)[0][2]
                    except Exception as exc:
                        take_qty = 0
                    if take_qty != market_qty:
                        bot_trader.del_limit_order('Sell', reduce_only = True)
                        entry_price = floor(bot_trader.get_market_entry_price('long'))
                        take_profit_value = entry_price + TAKE_PROFIT
                        bot_trader.post_limit_order(percent_limit = 100,
                                                limit_price = take_profit_value,
                                                direction = 'short',
                                                reduce_only = True)
                except Exception as exc:
                    log_error.error(exc)
                    time.sleep(1)
            time.sleep(1)
            bot_trader.del_limit_order('Buy', reduce_only=False)
            log_info.info("bot came out of long!!!")


def trade_short(bot_trader):
    log_info.info("bot started working in short!!!")
    while True:
        market_qty = bot_trader.get_market_qty(direction='short', reduce_only = False)
        while market_qty == 0:
            new_limit_orders_price, del_limit_orders_id = define_level(bot_trader, "Sell")
            for index, value in enumerate(new_limit_orders_price):
                bot_trader.post_limit_order(percent_limit = index + 1,
                                        limit_price = value,
                                        direction = 'short',
                                        reduce_only = False)
            if len(del_limit_orders_id) > 0:
                bot_trader.del_limit_order("Sell", False, del_limit_orders_id)
            market_qty = bot_trader.get_market_qty(direction = 'short', reduce_only = False)
        else:
            log_info.info("bot entered the trade in short!!!")
            entry_price = floor(bot_trader.get_market_entry_price('short'))
            take_profit_value = entry_price - TAKE_PROFIT
            bot_trader.post_limit_order(percent_limit = 100, limit_price = take_profit_value,
                                    direction = 'long',
                                    reduce_only = True)
            last_limit_order = bot_trader.get_price_last_draw_limit_order("Sell", False)
            bot_trader.stop_price_long = last_limit_order + STOP_LOSS
            bot_trader.put_stop_loss(stop_loss = bot_trader.stop_price_long, side = 'Sell')
            market_qty = bot_trader.get_market_qty(direction='short', reduce_only = False)
            qty_limit_orders_start = bot_trader.get_qty_limits_order('Sell')
            log_info.info("bot arranged extras and stop losses in short!!!")
            while market_qty != 0:
                try:
                    time.sleep(0.5)
                    qty_limit_orders = bot_trader.get_qty_limits_order('Sell')
                    if qty_limit_orders is not None:
                        if qty_limit_orders_start > qty_limit_orders:
                            qty_limit_orders_start = qty_limit_orders
                            bot_trader.del_limit_order('Buy', reduce_only = True)
                            entry_price = floor(bot_trader.get_market_entry_price('short'))
                            take_profit_value = entry_price - TAKE_PROFIT
                            bot_trader.post_limit_order(percent_limit = 100,
                                                    limit_price = take_profit_value,
                                                    direction = 'long',
                                                    reduce_only = True)
                            log_info.info("bot collected an additional short!!!")
                    time.sleep(1)
                    market_qty = bot_trader.get_market_qty(direction='short', reduce_only = False)
                    try:
                        list_take = bot_trader.get_info_open_limit_orders(direction='Buy', reduce_only = True)[0][2]
                    except Exception as exc:
                        take_qty = 0
                    if take_qty != market_qty:
                        bot_trader.del_limit_order('Buy', reduce_only = True)
                        entry_price = floor(bot_trader.get_market_entry_price('short'))
                        take_profit_value = entry_price - TAKE_PROFIT
                        bot_trader.post_limit_order(percent_limit = 100,
                                                limit_price = take_profit_value,
                                                direction = 'long',
                                                reduce_only = True)
                except Exception as exc:
                    log_error.error(exc)
                    time.sleep(1)
            time.sleep(1)
            bot_trader.del_limit_order('Sell', reduce_only=False)
            log_info.info("bot came out of short!!!")
  

def runStretagy(api_key, api_secret, symbol, proxy, interval):
    bot_trader = BotTrader(api_key, api_secret, MODE, symbol, proxy, interval)

    process_long = Process(target=trade_long, args=[bot_trader])
    process_short = Process(target=trade_short, args=[bot_trader])

    process_watcher_danger_long = Process(target=watch_out_danger_long, args=[bot_trader])
    process_watcher_danger_short = Process(target=watch_out_danger_short, args=[bot_trader])

    process_long.start()
    process_short.start()
    process_watcher_danger_long.start()
    process_watcher_danger_short.start()

    


