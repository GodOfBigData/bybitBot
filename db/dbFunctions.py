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
    session.execute(f"INSERT INTO {tableNameUsers}(username, api_key, api_secret, proxy, timeCreated)"
    + f"VALUES ('{username}', '{api_key}', '{api_secret}', '{proxy}', {timestampe});")

@decorateSessions
def getUsersInfo(session):
    info = session.execute(f"select * from {tableNameUsers};").fetchall()
    return info

@decorateSessions
def createTableInfoUser(session):
    try:
        tables = list(session.execute("SELECT * FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';").fetchall()[0])
        if tableNameUsers not in tables:
            session.execute(f"create table {tableNameUsers}(username character varying," 
                        "api_key character (18), api_secret character (36), proxy character varying," 
                        "timeCreated integer);")
        else:
            print("Table exist")
    except Exception as exc:
        print(exc)


