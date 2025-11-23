@echo off
chcp 65001 >nul
echo 安装币安量化交易平台...
echo.

echo [1/1] 安装Python依赖...
cd backend
pip install -r requirements.txt
cd ..

echo.
echo 安装完成！
echo 运行 start.bat 启动平台
echo.
pause
