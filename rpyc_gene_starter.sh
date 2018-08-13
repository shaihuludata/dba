#!/bin/bash
echo "starting server" && python3.6 ./rpyc_srv.py &
echo "starting genetic" && python3.6 ./genetic.py &
echo "starting client" && python3.6 ./rpyc_cli.py

#ps -A | grep -E "(12345|18811|9090)"
