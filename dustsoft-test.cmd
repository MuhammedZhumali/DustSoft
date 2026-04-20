@echo off
setlocal

if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0src"
)

set "LOCAL_VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%LOCAL_VENV_PYTHON%" (
    set "PYTHON_EXE=%LOCAL_VENV_PYTHON%"
    goto run_tests
)

set "PARENT_VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if exist "%PARENT_VENV_PYTHON%" (
    set "PYTHON_EXE=%PARENT_VENV_PYTHON%"
    goto run_tests
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    goto run_tests
)

python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto run_tests
)

echo Python 3 was not found. Install Python 3.11+ or create a .venv.
exit /b 9009

:run_tests
echo Running compile check...
%PYTHON_EXE% -m compileall src tests
if errorlevel 1 exit /b %ERRORLEVEL%

echo Running unit tests...
%PYTHON_EXE% -m unittest discover -s tests
exit /b %ERRORLEVEL%
