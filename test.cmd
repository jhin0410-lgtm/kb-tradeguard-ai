@echo off
setlocal
cd /d "%~dp0"
python -m pytest -q
if errorlevel 1 exit /b %errorlevel%
python -m compileall -q app.py src tests scripts
if errorlevel 1 exit /b %errorlevel%
python -c "import app; import src"
exit /b %errorlevel%
