from bots.bots import *
from bots.config import key_coinMarket
from time import sleep
import multiprocessing

LONG = "LONG"
SHORT = "SHORT"
procLong = None
procShort = None
LIMITS_INFO = [(2, 100), (4, 300)]



def check_intersection(bot_analyst, last_ma, last_ema, need_dif):
    ma, ema = bot_analyst.getCurrentMaEma() # take current values
    dif_metrics_short = ma - ema
    dif_metrics_long = ema - ma
    if last_ema > last_ma and dif_metrics_short > need_dif:
        return SHORT
    elif last_ema < last_ma and dif_metrics_long > need_dif:
        return LONG
    else:
        return None


def checkGlobalMetrics(direction):
    analyst_onhcain_metrics = analystOnhcainMetrics(key_coinMarket) # create analyst global metrics
    eth_dominance, eth_dominance_yesterday, last_updated = analyst_onhcain_metrics.getInformationEth() # take global metrics
    if direction == LONG:
        if eth_dominance < eth_dominance_yesterday:
            return True
        else:
            return False
    else:
        if eth_dominance > eth_dominance_yesterday:
            return True
        else:
            return False


def runFlatTrading(api_key, api_secret, symbol, proxy):
    botTrader = FlatBotTrader(api_key, api_secret, symbol, proxy, 60, LIMITS_INFO) # create trader bot
    procLong.start()
    procShort.start()


def runIntersectionTrading(api_key, api_secret, symbol, proxy, direction):
    botTrader = FlatBotTrader(api_key, api_secret, symbol, proxy, 60, LIMITS_INFO) # create trader bot
    if direction == LONG:
        procLong.start()
    else:
        procShort.start()

def stopTrading():
    procLong.terminate()
    procShort.terminate()



def runIntersectionStrategy(api_key, api_secret, proxy, symbol, interval):
    procLong = multiprocessing.Process(target=botTrader.work_long)
    procShort = multiprocessing.Process(target=botTrader.work_short)
    bot_analyst = botAnalyst(api_key, api_secret, symbol, interval, proxy) # create market analyst bot 
    ma, ema = bot_analyst.getCurrentMaEma() # take current values
    direction = None
    solution_trade = False
    flat_trading_is_runing = False
    while True:
        direction = check_intersection(bot_analyst, ma, ema, 40)
        if direction == LONG:
            solution_trade = checkGlobalMetrics(LONG)
        if direction == SHORT:
            solution_trade = checkGlobalMetrics(SHORT)
        if solution_trade == True:
            stopTrading()
            runIntersectionTrading(api_key, api_secret, symbol, proxy, direction)
            solution_trade = False
            direction = None
            flat_trading_is_runing = False
        sleep(1)
        if flat_trading_is_runing is False:
            flat_trading_is_runing = True
            """
            run thread trading
            """
            stopTrading()
            runFlatTrading(api_key, api_secret, symbol, proxy)
    


    # sleep(30)

# eth_dominance': 17.334679350939,
#  'eth_dominance_24h_percentage_change': 0.176144010939,
#  'eth_dominance_yesterday': 17.15853534,
#  'last_updated'