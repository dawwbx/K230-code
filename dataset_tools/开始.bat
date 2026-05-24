@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "SRC_DIR=C:\Users\pc\Desktop\p"

:MENU
cls
echo ============================================
echo   K230 dataset workflow
echo ============================================
echo.
echo   Source folder: %SRC_DIR%  (auto-prompt if missing)
echo.
echo   [1] Auto-label  (p\*.jpg -^> dataset)
echo   [2] Manual fix  (review/edit boxes)
echo   [3] Pack ZIP    (upload to AI Cube)
echo   [4] Clear dataset folder
echo   [Q] Quit
echo.
set /p choice="Choose: "

if /i "%choice%"=="1" goto AUTO
if /i "%choice%"=="2" goto FIX
if /i "%choice%"=="3" goto PACK
if /i "%choice%"=="4" goto CLEAR
if /i "%choice%"=="q" exit /b
goto MENU

:AUTO
echo.
python 1_auto_label.py
echo.
pause
goto MENU

:FIX
echo.
python 4_labelfix.py
echo.
pause
goto MENU

:PACK
echo.
python 3_pack_for_aicube.py
echo.
pause
goto MENU

:CLEAR
echo.
echo What to clear?
echo   [1] dataset/ only (labels)
echo   [2] dataset/ + source photos in %SRC_DIR%
echo   [3] Cancel
set /p sub="Choose: "
if "%sub%"=="3" goto MENU
if "%sub%"=="" goto MENU
if not "%sub%"=="1" if not "%sub%"=="2" goto MENU

set /p ok="Really clear? (y/N): "
if /i not "%ok%"=="y" goto MENU

if exist "dataset\images"     rmdir /s /q "dataset\images"
if exist "dataset\xml"        rmdir /s /q "dataset\xml"
if exist "dataset\labels.txt" del   /q   "dataset\labels.txt"
echo dataset/ cleared.

if "%sub%"=="2" (
    if exist "%SRC_DIR%" (
        del /q "%SRC_DIR%\*.jpg"  2>nul
        del /q "%SRC_DIR%\*.jpeg" 2>nul
        del /q "%SRC_DIR%\*.png"  2>nul
        del /q "%SRC_DIR%\*.JPG"  2>nul
        del /q "%SRC_DIR%\*.JPEG" 2>nul
        del /q "%SRC_DIR%\*.PNG"  2>nul
        echo Source photos in %SRC_DIR% deleted.
    ) else (
        echo %SRC_DIR% not found, skipped.
    )
)
pause
goto MENU
