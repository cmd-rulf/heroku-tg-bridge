FROM python:3.10-slim
WORKDIR / app
COPY . /app/
COPY requirements.txt /requirements.txt
RUN pip3 install -U -r requirements.txt
CMD ["python3", "bot.py"] 
