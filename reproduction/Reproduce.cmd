@echo off
"%~dp0vendor\python312\python.exe" -I -B "%~dp0reproduce.py" %*
exit /b %ERRORLEVEL%
