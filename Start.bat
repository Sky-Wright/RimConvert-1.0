@echo off
setlocal enabledelayedexpansion

REM =============================================================================
REM RimWorld Texture Optimizer - Setup and Launch Script
REM =============================================================================

title RimWorld Texture Optimizer
color 0A

echo.
echo ===============================================================================
echo   RimWorld Texture Optimizer
echo   A modern Rimworld texture optimization tool.
echo   Made for the community, by Sky
echo ===============================================================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.8 or later from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found: 
python --version

REM Check if virtual environment exists
if not exist ".venv" (
    echo.
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate virtual environment
    pause
    exit /b 1
)

REM Check and install required packages
echo.
echo Checking required packages...

REM Check for Pillow
python -c "import PIL" 2>nul
if errorlevel 1 (
    echo Installing Pillow...
    pip install Pillow
    if errorlevel 1 (
        echo Failed to install Pillow
        pause
        exit /b 1
    )
)

REM Check for PyInstaller (needed for building executables)
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install PyInstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo All dependencies satisfied

REM Check for texconv.exe
if not exist "compressors\texconv.exe" (
    echo.
    echo WARNING: texconv.exe not found in compressors\
    echo This tool is required for texture conversion.
    echo Please ensure you have the compressor tools available.
    echo.
    pause
    exit /b 1
) else (
    echo texconv.exe found
)

:menu
echo.
echo ===============================================================================
echo Choose an option:
echo.
echo 1. Launch GUI
echo 2. Build Standalone Executable
echo 3. Exit
echo.
set /p choice=Enter your choice (1-3): 

if "%choice%"=="1" goto launch_gui
if "%choice%"=="2" goto build_gui_exe
if "%choice%"=="3" goto exit_script

echo Invalid choice. Please try again.
goto menu

:launch_gui
echo.
echo Launching GUI...
python rimworld_gui.py
if errorlevel 1 (
    echo.
    echo GUI launch failed. Check error messages above.
    pause
)
goto menu

:build_gui_exe
echo.
echo Building standalone GUI executable...
echo This will create RimWorldOptimizer.exe in the dist folder
echo.
python -m PyInstaller RimWorldOptimizer.spec
if errorlevel 1 (
    echo Build failed
    pause
) else (
    echo.
    echo Build successful!
    echo.
    echo DEPLOYMENT READY:
    echo Copy the entire 'dist' folder and rename it for deployment.
    echo The executable and all dependencies are included.
    echo.
    pause
)
goto menu

:exit_script
echo.
echo Thank you for using RimWorld Texture Optimizer!
exit /b 0