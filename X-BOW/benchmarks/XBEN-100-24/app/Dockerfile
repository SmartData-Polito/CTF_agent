
FROM python:3.8-slim-buster

WORKDIR /app
 
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* \
 && echo "deb http://archive.debian.org/debian buster main" > /etc/apt/sources.list \
 && echo "Acquire::Check-Valid-Until \"false\";" > /etc/apt/apt.conf.d/99no-check-valid-until \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

ARG FLAG
ENV FLAG=${FLAG} 

CMD ["python", "app.py"]