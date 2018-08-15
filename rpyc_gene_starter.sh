#!/bin/bash
echo "starting genetic" && python3.6 ./genetic.py & sleep 3
echo "starting server" && python3.6 ./rpyc_srv.py & sleep 3
echo "starting client" && python3.6 ./rpyc_cli.py

#ss -ptan | grep -E "(12345|18811|9090)"
