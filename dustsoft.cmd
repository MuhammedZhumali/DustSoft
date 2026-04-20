@echo off
setlocal

set "PYTHON_EXE=C:\Users\Muhalek\AppData\Local\Python\bin\python.exe"
set "PYTHONPATH=%~dp0src"

"%PYTHON_EXE%" "%~dp0src\main.py" %*
