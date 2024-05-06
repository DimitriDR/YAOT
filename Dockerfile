FROM alpine:3.19

WORKDIR /app

COPY main.py .
COPY requirements.txt .

RUN apk add --no-cache python3 py3-pip chromium chromium-chromedriver

RUN python3 -m venv .venv
RUN .venv/bin/pip install --no-cache-dir --upgrade pip
RUN .venv/bin/pip install --no-cache-dir -r requirements.txt

CMD echo "*/15 * * * * /app/.venv/bin/python /app/main.py  >> /proc/1/fd/1 2>&1" > /etc/crontabs/root && crond -f
