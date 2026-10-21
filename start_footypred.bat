@echo off
rem Double-click to open footypred in your browser (Windows).
rem Keep the black window open while you use the app; close it to stop.
title footypred
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% --version >nul 2>nul || goto nopython
%PY% -c "import yaml, pandas, lightgbm, rapidfuzz, openpyxl" >nul 2>nul || goto install
:run
echo Starting footypred - your browser opens in a moment.
echo Keep this window open while you use the app.
%PY% -m footypred app
pause
exit /b
:install
echo First start: installing the packages footypred needs (takes a few minutes) ...
%PY% -m pip install -r requirements.txt || goto failed
%PY% -m pip install -e . || goto failed
goto run
:nopython
echo Python was not found. Install Python 3 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup, then double-click this file again.
pause
exit /b 1
:failed
echo Installing the packages failed - see the messages above.
pause
exit /b 1
