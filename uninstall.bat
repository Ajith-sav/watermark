@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Uninstaller for Desktop Watermark (DesktopWatermark.exe)
REM ============================================================
REM  This script:
REM    1. Stops the running watermark process, if any.
REM    2. Removes any auto-start entries it may have created
REM       (Startup folder shortcut, Task Scheduler task,
REM       Registry Run key) under the common default names.
REM    3. Optionally deletes the exe/install folder itself.
REM
REM  Run this on the SAME Windows machine where the watermark
REM  is installed. Right-click -> "Run as administrator" is
REM  recommended so it can also remove an elevated Task
REM  Scheduler entry if one exists.
REM ============================================================

echo ============================================================
echo  Desktop Watermark - Uninstaller
echo ============================================================
echo.

REM ---- Step 1: stop the running process -----------------------
echo Stopping DesktopWatermark.exe if it is running...
taskkill /IM "DesktopWatermark.exe" /F >nul 2>nul
if errorlevel 1 (
    echo   - Not currently running ^(or already stopped^).
) else (
    echo   - Stopped.
)
echo.

REM ---- Step 2: remove Startup folder shortcut -------------------
echo Checking Startup folder for a shortcut...
set "STARTUP_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DesktopWatermark.lnk"
if exist "%STARTUP_LNK%" (
    del /f /q "%STARTUP_LNK%"
    echo   - Removed: %STARTUP_LNK%
) else (
    echo   - No shortcut found at the default name/location.
    echo     ^(If you named it differently, remove it manually from:^)
    echo     %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
)
echo.

REM ---- Step 3: remove Task Scheduler task ------------------------
echo Checking Task Scheduler for "Desktop Watermark" task...
schtasks /query /tn "Desktop Watermark" >nul 2>nul
if errorlevel 1 (
    echo   - No matching scheduled task found.
) else (
    schtasks /delete /tn "Desktop Watermark" /f >nul 2>nul
    if errorlevel 1 (
        echo   - [WARNING] Found the task but could not delete it.
        echo     Try re-running this script "as administrator".
    ) else (
        echo   - Removed scheduled task "Desktop Watermark".
    )
)
echo.

REM ---- Step 4: remove Registry Run key ----------------------------
echo Checking Registry Run key...
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DesktopWatermark" >nul 2>nul
if errorlevel 1 (
    echo   - No matching Registry Run entry found.
) else (
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DesktopWatermark" /f >nul 2>nul
    echo   - Removed Registry Run entry "DesktopWatermark".
)
echo.

REM ---- Step 5: optionally delete the exe / install folder ----------
echo ============================================================
set /p DELETE_FILES="Delete the DesktopWatermark.exe file and this folder's build output too? (y/N): "
if /i "%DELETE_FILES%"=="y" (
    cd /d "%~dp0"
    if exist "dist\DesktopWatermark.exe" (
        del /f /q "dist\DesktopWatermark.exe"
        echo   - Deleted dist\DesktopWatermark.exe
    )
    if exist "DesktopWatermark.exe" (
        del /f /q "DesktopWatermark.exe"
        echo   - Deleted DesktopWatermark.exe
    )
    echo.
    echo If you installed a copy elsewhere ^(e.g. Program Files, a shared
    echo network folder, etc.^), delete that copy manually as well.
) else (
    echo   - Skipped file deletion. You can delete DesktopWatermark.exe
    echo     manually whenever you like.
)

echo.
echo ============================================================
echo  Uninstall steps complete.
echo ============================================================
pause