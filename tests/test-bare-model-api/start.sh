#!/usr/bin/env bash
set -e

uwsgi --strict --http 0.0.0.0:5000 --processes 4 --wsgi-file app.py &

exec tcpdump -vvvv -n