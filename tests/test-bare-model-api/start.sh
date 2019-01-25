#!/usr/bin/env bash
set -e

uwsgi --strict --http 0.0.0.0:5000 --processes 4 --wsgi-file app.py >> /proc/1/fd/1 2>&1 &

exec tcpdump -vvv -n dst port 5000