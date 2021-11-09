FROM python:3.8.3-slim-buster AS compile
COPY requirements.txt .
RUN apt update \
 && apt install --no-install-recommends -y ca-certificates git openssl \
 && apt install --no-install-recommends -y libffi-dev libssl-dev build-essential python3-pip python3-dev python2 make g++ \
 && pip install --user -r requirements.txt

FROM python:3.8.3-slim-buster AS build
COPY . /app
WORKDIR /app
COPY --from=compile /root/.local /root/.local
RUN apt update \
 && apt install --no-install-recommends -y opencc libzbar0 \
 && apt autoremove --purge \
 && apt clean all \
 && rm -rf /var/lib/apt/lists/*
CMD ["python3", "main.py"]
