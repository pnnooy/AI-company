@echo off
cd /d "%~dp0"
echo.
echo ======================================
echo   桌面学术助手 · 控制面板
echo ======================================
echo.
echo   启动中... 浏览器将自动打开
echo.
start "" http://localhost:8000
python mock_server.py
pause