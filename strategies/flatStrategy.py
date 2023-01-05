from bots.bots import *
from bots.config import key_coinMarket
import multiprocessing


def runFlatStrategy(api_key, api_secret, proxy, symbol, interval):
    limits_info = [(2, 100), (4, 300)]
    botTrader = FlatBotTrader(api_key, api_secret, symbol, proxy, 60, limits_info) # create trader bot
    procLong = multiprocessing.Process(target=botTrader.work_long)
    procShort = multiprocessing.Process(target=botTrader.work_short)
    procLong.start()
    procShort.start()
