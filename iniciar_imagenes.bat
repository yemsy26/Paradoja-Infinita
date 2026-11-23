@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Paradoja Infinita - imagenes

echo ============================================
echo   PARADOJA INFINITA - imagenes para el feed
echo ============================================

rem ---------- 1. Python ----------
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY goto :install_python
goto :have_python

:install_python
echo [setup] Python no encontrado. Instalando con winget...
where winget >nul 2>&1 || (echo ERROR: winget no esta disponible. Instala Python 3.10+ desde python.org y vuelve a ejecutar. & goto :fail)
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo.
echo Python instalado. CIERRA esta ventana y vuelve a ejecutar iniciar_imagenes.bat para que Windows actualice el PATH.
goto :fail

:have_python
rem ---------- 2. Entorno virtual ----------
if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creando entorno virtual .venv ...
    %PY% -m venv .venv || goto :fail
)

rem ---------- 3. Dependencias (solo si cambiaron o es la primera vez) ----------
set "STAMP=.venv\requirements.installed"
fc /b requirements.txt "%STAMP%" >nul 2>&1
if errorlevel 1 (
    echo [setup] Instalando dependencias de Python ...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
    copy /y requirements.txt "%STAMP%" >nul
)

rem ---------- 4. Generar las imagenes (sin argumentos: menu interactivo) ----------
echo.
".venv\Scripts\python.exe" generador_imagenes.py %*
if errorlevel 1 goto :fail

echo.
echo Listo. Imagenes en: %~dp0output_imagenes
if exist "%~dp0output_imagenes" explorer "%~dp0output_imagenes"
pause
exit /b 0

:fail
echo.
echo El proceso no termino correctamente.
pause
exit /b 1
