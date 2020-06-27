@echo off

echo Correct package version in setup.py, then proceed ...
pause >nul
echo.

python setup.py bdist_wheel

echo.
pause