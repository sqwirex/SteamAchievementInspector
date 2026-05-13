@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo === SteamAchievementInspector build started ===

if not exist "main.py" (
    echo main.py not found. Put this bat file in the same folder as main.py
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo requirements.txt not found. Put this bat file in the same folder as requirements.txt
    pause
    exit /b 1
)

if not exist "ve\Scripts\python.exe" (
    python -m venv ve
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call "ve\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

python -m pip install pyinstaller
if errorlevel 1 (
    echo Failed to install pyinstaller.
    pause
    exit /b 1
)

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "SteamAchievementInspector.spec" del /f /q "SteamAchievementInspector.spec"

if exist "assets\app.ico" (
    pyinstaller --noconfirm --clean --onefile --windowed --name SteamAchievementInspector --icon=assets/app.ico --add-data "assets/app.ico;assets" main.py
) else (
    pyinstaller --noconfirm --clean --onefile --windowed --name SteamAchievementInspector main.py
)

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo === Refreshing Windows icon cache / Explorer ===

taskkill /f /im explorer.exe >nul 2>nul

del /f /q "%LOCALAPPDATA%\IconCache.db" >nul 2>nul
del /f /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*" >nul 2>nul
del /f /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache*" >nul 2>nul

start explorer.exe

echo.
echo === Build finished ===
echo EXE: dist\SteamAchievementInspector.exe
echo Explorer restarted and icon cache cleanup attempted.
pause
endlocal