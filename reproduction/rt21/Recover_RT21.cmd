@echo off
"%~dp0vendor\python313\bin\python.exe" -I -B "%~dp0recover.py" %*
exit /b %ERRORLEVEL%
