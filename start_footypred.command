#!/bin/bash
# Double-click to open footypred in your browser (macOS; on Linux run ./start_footypred.command).
# Keep the window open while you use the app; close it to stop.
cd "$(dirname "$0")" || exit 1
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Enter to close"; exit 1
fi
if ! "$PY" -c "import yaml, pandas, lightgbm, rapidfuzz, openpyxl" >/dev/null 2>&1; then
  echo "First start: installing the packages footypred needs (takes a few minutes) ..."
  if ! { "$PY" -m pip install -r requirements.txt && "$PY" -m pip install -e . ; }; then
    echo "Installing the packages failed - see the messages above."
    read -r -p "Press Enter to close"; exit 1
  fi
fi
echo "Starting footypred - your browser opens in a moment. Keep this window open while you use it."
"$PY" -m footypred app
