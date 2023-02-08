from  strategies.levelsSrategy import runStretagy
from configs.config import api_key, api_secret, proxy, currency, interval


if __name__ == "__main__":
    runStretagy(api_key, api_secret, currency, proxy, interval)
    