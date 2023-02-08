FROM python:3.10 as builder

RUN mkdir -p /logs

RUN mkdir -p /configs

RUN touch  configs/config.py

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY  bots bots

COPY  db db

COPY strategies strategies

COPY main.py main.py

CMD [ "sleep", "30s"]

CMD [ "python3", "main.py"]

