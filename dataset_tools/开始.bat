@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

:MENU
cls
echo ============================================
echo   K230 dataset workflow
echo ============================================
echo.
echo   [1] Auto-label  (source photos -^> dataset)
echo   [2] Manual fix  (review/edit boxes)
echo   [3] Pack ZIP    (upload to AI Cube)
echo   [4] Clear       (dataset, and/or source photos)
echo   [5] HSV picker  (tune/add a class by clicking on the object)
echo   [Q] Quit
echo.
set /p choice="Choose: "

if /i "%choice%"=="1" goto AUTO
if /i "%choice%"=="2" goto FIX
if /i "%choice%"=="3" goto PACK
if /i "%choice%"=="4" goto CLEAR
if /i "%choice%"=="5" goto PICK
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

:PICK
echo.
python 5_hsv_picker.py
echo.
pause
goto MENU

:CLEAR
echo.
python _clear_helper.py
echo.
pause
goto MENU
