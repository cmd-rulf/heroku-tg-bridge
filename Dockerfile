FROM python:3.10-slim
WORKDIR / app
COPY . /app/
COPY requirements.txt 
RUN pip3 install -U -r requirements.txt
CMD ["python3", "bot.py"] 

FROM python:3.9
WORKDIR / app
COPY . /app/
RUN pip3 install -U pip && pip3 install -U -r requirements.txt
CMD ["python3", "bot.py"] 
