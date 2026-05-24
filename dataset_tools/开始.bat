@echo off
chcp 65001 >nul
cd /d "%~dp0"

:MENU
cls
echo ============================================
echo   K230 dataset workflow
echo ============================================
echo.
echo   Source folder: C:\Users\pc\Desktop\p
echo.
echo   [1] Auto-label  (p\*.jpg  ->  dataset)
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
echo This will delete dataset\images and dataset\xml
set /p ok="Are you sure? (y/N): "
if /i not "%ok%"=="y" goto MENU
if exist "dataset\images" rmdir /s /q "dataset\images"
if exist "dataset\xml"    rmdir /s /q "dataset\xml"
if exist "dataset\labels.txt" del /q "dataset\labels.txt"
echo Cleared.
pause
goto MENU
