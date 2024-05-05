FROM python:3.11-slim

WORKDIR /app

COPY config.toml /app
COPY main.py /app
COPY requirements.txt /app
COPY marks.json /app

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

ENV PATH="/root/.local/bin:${PATH}"

CMD ["python", "-u", "main.py"]