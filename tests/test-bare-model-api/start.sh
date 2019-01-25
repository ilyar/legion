#!/usr/bin/env bash

python app.py >> /proc/1/fd/1 2>&1 &

exec tcpdump -n dst port 5000