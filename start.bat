@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo 请安装 Python 3.10 或更新版本，并加入 PATH。
  pause
  exit /b 1
)
echo 浏览器访问 http://127.0.0.1:8765
python app.py
pause
