@echo off
setlocal enabledelayedexpansion

set "APP_NAME=PrismAR"
set "VERSION=v1.0"
set "PROJECT_ROOT=%~dp0"
set "ASSETS_DIR=%PROJECT_ROOT%assets"
set "MODEL_PATH=%ASSETS_DIR%\hand_landmarker.task"
set "MODEL_URL=https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
set "DIST_EXE=%PROJECT_ROOT%dist\%APP_NAME%.exe"
set "RELEASE_ROOT=%PROJECT_ROOT%release"
set "RELEASE_DIR=%RELEASE_ROOT%\%APP_NAME%-%VERSION%"
set "ZIP_PATH=%RELEASE_ROOT%\%APP_NAME%-%VERSION%.zip"

echo.
echo === %APP_NAME% Windows Build ===
echo Project: %PROJECT_ROOT%
echo.

cd /d "%PROJECT_ROOT%"

if not exist "%ASSETS_DIR%" mkdir "%ASSETS_DIR%"

if not exist "%MODEL_PATH%" (
    echo MediaPipe hand model not found. Downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%MODEL_URL%' -OutFile '%MODEL_PATH%'"
    if errorlevel 1 exit /b 1
)

echo Building one-file windowed EXE...
python -m PyInstaller --noconfirm --clean PrismAR.spec
if errorlevel 1 exit /b 1

if not exist "%DIST_EXE%" (
    echo Build failed: "%DIST_EXE%" was not created.
    exit /b 1
)

echo Preparing release folder...
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%"
mkdir "%RELEASE_DIR%"

copy /y "%DIST_EXE%" "%RELEASE_DIR%\%APP_NAME%.exe" >nul
copy /y "%PROJECT_ROOT%README.md" "%RELEASE_DIR%\README.md" >nul

if exist "%PROJECT_ROOT%LICENSE" (
    copy /y "%PROJECT_ROOT%LICENSE" "%RELEASE_DIR%\LICENSE" >nul
)

rem The EXE already contains bundled assets. The external assets folder is also
rem included in the release ZIP as a transparent backup/manual fallback.
mkdir "%RELEASE_DIR%\assets"
copy /y "%MODEL_PATH%" "%RELEASE_DIR%\assets\hand_landmarker.task" >nul
if exist "%ASSETS_DIR%\README.md" (
    copy /y "%ASSETS_DIR%\README.md" "%RELEASE_DIR%\assets\README.md" >nul
)

if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"

echo Creating ZIP release...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo EXE: %DIST_EXE%
echo Release folder: %RELEASE_DIR%
echo ZIP: %ZIP_PATH%
echo.

endlocal
