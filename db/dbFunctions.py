from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from db.config import * 

engine = create_engine("postgresql://" + username + ":" + password + "@" + host + ":" + port + "/" + dbName)

def decorateSessions(function_dataBase):
    def openCloseConnection(*args):
        Session = sessionmaker(engine)
        session = Session()  
        result = function_dataBase(*args, session)
        session.commit()
        session.close()
        return result
    return openCloseConnection


@decorateSessions
def addUser(username, api_key, api_secret, proxy, session):
    date = datetime.now()
    timestampe = int(date.timestamp())
    session.execute("INSERT INTO usersInfo(username, api_key, api_secret, proxy, timeCreated)"
    + f"VALUES ('{username}', '{api_key}', '{api_secret}', '{proxy}', {timestampe});")

@decorateSessions
def getUsersInfo(session):
    info = session.execute("select * from usersInfo;").fetchall()
    return info


