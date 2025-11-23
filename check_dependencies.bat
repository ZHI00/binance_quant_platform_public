@echo off
chcp 65001 >nul
echo ========================================
echo 后端依赖检查工具
echo ========================================
echo.

py check_dependencies.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 按任意键退出...
    pause >nul
    exit /b 1
)

echo.
echo 按任意键退出...
pause >nul
