from  strategies.levelsSrategy import runStretagy
from configs.config import api_key, api_secret, proxy, currency, interval
from time import sleep


if __name__ == "__main__":
    # sleep(30)
    runStretagy(api_key, api_secret, currency, proxy, interval)
    