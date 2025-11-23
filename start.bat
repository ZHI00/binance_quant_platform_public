@echo off
chcp 65001 >nul
echo 启动币安量化交易平台...
echo.

cd ./backend
py run.py

pause
