@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Build script for Desktop Watermark -> standalone .exe
REM  Run this on a WINDOWS machine with Python installed.
REM ============================================================

REM Always run from the folder this .bat file lives in, regardless of
REM where it was double-clicked from.
cd /d "%~dp0"
echo Working folder: %cd%
echo.

REM ---- Step 0: confirm required files are present ----------------
if not exist "watermark.py" (
    echo [ERROR] watermark.py not found in this folder.
    echo Make sure build_exe.bat is in the SAME folder as:
    echo   - watermark.py
    echo   - watermark.spec
    echo   - watermark.manifest
    goto :fail
)
if not exist "watermark.spec" (
    echo [ERROR] watermark.spec not found in this folder.
    goto :fail
)
if not exist "watermark.manifest" (
    echo [ERROR] watermark.manifest not found in this folder.
    goto :fail
)

REM ---- Step 1: confirm Python is available ------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "python" was not found on PATH.
    echo Install Python from https://www.python.org/downloads/
    echo and make sure to check "Add python.exe to PATH" during install.
    goto :fail
)

echo Using Python:
python --version
echo.

REM ---- Step 2: install/upgrade required packages -------------------
echo Installing/upgrading required packages...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip. Check your internet connection.
    goto :fail
)

python -m pip install --upgrade pyinstaller pywin32 psutil pystray pillow
if errorlevel 1 (
    echo [ERROR] Failed to install one or more required packages.
    echo Check the error message above ^(internet connection, proxy,
    echo permissions, etc.^) and try again.
    goto :fail
)
echo.

REM ---- Step 3: clean any previous build output ---------------------
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM ---- Step 4: run PyInstaller --------------------------------------
echo Building DesktopWatermark.exe ...
echo.
python -m PyInstaller --noconfirm --clean watermark.spec
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller reported an error - see the output above
    echo for details ^(scroll up^). Common causes:
    echo   - A typo or missing import in watermark.py
    echo   - watermark.manifest is not valid XML
    echo   - Antivirus quarantined a file during the build
    goto :fail
)

REM ---- Step 5: confirm the exe actually exists ----------------------
if not exist "dist\DesktopWatermark.exe" (
    echo.
    echo [ERROR] Build finished without an explicit error, but
    echo dist\DesktopWatermark.exe was not created. Scroll up through
    echo the PyInstaller output above for warnings, or check the build
    echo log at: build\DesktopWatermark\warn-DesktopWatermark.txt
    goto :fail
)

echo.
echo ============================================================
echo  SUCCESS - exe created at: dist\DesktopWatermark.exe
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ============================================================
echo  BUILD FAILED - see the error above.
echo  This window will stay open - read the messages, then press
echo  any key to close.
echo ============================================================
pause
exit /b 1