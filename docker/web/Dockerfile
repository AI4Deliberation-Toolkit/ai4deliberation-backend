FROM python:3.12-slim

COPY ./requirements.txt /usr/src/app/
WORKDIR /usr/src/app/
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get insall -y --no-install-recommends netcat-traditional && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app/

RUN chmod +x ./docker/web/entrypoint.sh
EXPOSE 8000
ENTRYPOINT [ "./docker/web/entrypoint.sh" ]