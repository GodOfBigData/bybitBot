from strategies.intersectionMovingAverages import runIntersectionStrategy
from db.dbFunctions import getUsersInfo


if __name__ == "__main__":
    userInfo = getUsersInfo()[0]
    api_key = userInfo[1]
    api_secret = userInfo[2]
    proxy = userInfo[3]
    runIntersectionStrategy(api_key, api_secret, proxy, "BTCUSDT", 60)

