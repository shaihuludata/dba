FROM python:3
MAINTAINER sw

ADD ./rpyc_cli.py /
RUN mkdir -p /usr/src/dba
WORKDIR /usr/src/dba
COPY requirements.txt /usr/src/dba/
RUN apt-get update && \
    apt-get install -y apt-utils && \
    apt-get install -y python3 python3-pip && \
#    apt-get -y install python3-numpy, python3-simpy, python3-sympy
    apt-get install -y python3-tk
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . /usr/src/dba
CMD ["python3", "./rpyc_cli.py"]

#docker build -t pydba .
#docker run -ti pydba:latest
