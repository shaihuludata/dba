FROM python:3
MAINTAINER sw

RUN mkdir -p /usr/src/dba
WORKDIR /usr/src/dba
COPY requirements.txt /usr/src/dba/
RUN apt-get update && \
    apt-get install -y apt-utils && \
    apt-get install -y python3 python3-pip && \
#    apt-get -y install python3-numpy, python3-simpy, python3-sympy
    pip3 install --no-cache-dir -r requirements.txt

COPY . /usr/src/dba
CMD ["python3", "./main.py"]

#docker build -t pydba .
#docker run -ti pydba:latest
