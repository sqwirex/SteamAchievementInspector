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

taskkill /f /im SteamAchievementInspector.exe >nul 2>nul
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
echo === Build finished ===
echo EXE: dist\SteamAchievementInspector.exe
echo Opening dist and starting app...

start "" explorer.exe "%CD%\dist"
start "" "%CD%\dist\SteamAchievementInspector.exe"

endlocal
exit /b 0