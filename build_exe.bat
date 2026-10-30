@echo off
REM ============================================================
REM  RS-Uninstaller 单文件打包脚本
REM  前置：python -m pip install pyinstaller
REM  产物：dist\RS-Uninstaller-0.2.0.exe
REM ============================================================

set APP_NAME=RS-Uninstaller
set APP_VERSION=0.2.0

pyinstaller --noconfirm --clean --onefile --windowed ^
  --uac-admin ^
  --name "%APP_NAME%-%APP_VERSION%" ^
  --icon "res\icon.ico" ^
  --add-data "res\icon.ico;res" ^
  --collect-all nicegui ^
  --collect-all webview ^
  --collect-all pythonnet ^
  --collect-all clr_loader ^
  run.py

echo.
echo 输出：dist\%APP_NAME%-%APP_VERSION%.exe
pause
