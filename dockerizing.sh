#!/usr/bin/env bash

docker build -t pydba .

docker tag pydba localhost:5000/pydba

docker push localhost:5000/pydba

