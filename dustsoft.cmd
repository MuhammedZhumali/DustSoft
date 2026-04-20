@echo off
setlocal

if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0src"
)

set "LOCAL_VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%LOCAL_VENV_PYTHON%" (
    "%LOCAL_VENV_PYTHON%" "%~dp0src\main.py" %*
    exit /b %ERRORLEVEL%
)

set "PARENT_VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if exist "%PARENT_VENV_PYTHON%" (
    "%PARENT_VENV_PYTHON%" "%~dp0src\main.py" %*
    exit /b %ERRORLEVEL%
)

py -3 "%~dp0src\main.py" %*
if not errorlevel 9009 exit /b %ERRORLEVEL%

python "%~dp0src\main.py" %*
exit /b %ERRORLEVEL%
