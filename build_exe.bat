@echo off
rem Builds "Save Now.exe" - a single, shareable file with no dependencies.
setlocal
cd /d "%~dp0"

rem A running copy locks dist\Save Now.exe and the build fails on removing it.
echo Closing any running copy...
taskkill /f /im "Save Now.exe" >nul 2>&1

rem Stale bytecode can be bundled instead of the current source.
echo Clearing previous build output...
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo Generating icon...
py make_icon.py || goto :fail

echo Installing PyInstaller if needed...
py -m pip install --quiet --upgrade pyinstaller || goto :fail

echo Building executable...
py -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "Save Now" ^
  --icon app_icon.ico ^
  --add-data "app_icon.ico;." ^
  --add-data "app_icon.png;." ^
  --clean ^
  --noconfirm ^
  save_reminder.py || goto :fail

echo.
echo Done.  Share this file:  "%~dp0dist\Save Now.exe"
goto :eof

:fail
echo.
echo BUILD FAILED - see the messages above.
exit /b 1
