#!/bin/sh
set -e

Xvfb :99 -screen 0 1366x768x24 -nolisten tcp &

export DISPLAY=:99

# Espera o soquete do Xvfb aparecer, ate uns 5 segundos
i=0
while [ ! -e /tmp/.X11-unix/X99 ] && [ "$i" -lt 25 ]; do
  sleep 0.2
  i=$((i + 1))
done

exec python app.py
