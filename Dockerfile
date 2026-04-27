FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY . .

RUN mkdir -p /app/runtime

ENV USE_DEV_SERVER=0
EXPOSE 5555

CMD ["python", "web_server.py"]
