@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Paradoja Infinita

echo ============================================
echo   PARADOJA INFINITA - generador de videos
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
echo Python instalado. CIERRA esta ventana y vuelve a ejecutar iniciar.bat para que Windows actualice el PATH.
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

rem ---------- 4. FFmpeg (con NVENC) ----------
where ffmpeg >nul 2>&1 && where ffprobe >nul 2>&1 && goto :have_ffmpeg
call :find_ffmpeg
where ffmpeg >nul 2>&1 && goto :have_ffmpeg

echo [setup] FFmpeg no encontrado. Instalando con winget ^(Gyan.FFmpeg^)...
where winget >nul 2>&1 || (echo ERROR: winget no esta disponible. Instala FFmpeg manualmente y agregalo al PATH. & goto :fail)
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
call :find_ffmpeg
where ffmpeg >nul 2>&1 || (echo ERROR: FFmpeg se instalo pero no se localiza. Cierra esta ventana y ejecuta de nuevo. & goto :fail)

:have_ffmpeg
rem ---------- 5. Generar el video ----------
echo.
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto :fail

echo.
echo Listo. Videos en: %~dp0output
explorer "%~dp0output"
pause
exit /b 0

:fail
echo.
echo El proceso no termino correctamente.
pause
exit /b 1

rem ---------- subrutina: busca FFmpeg instalado por winget y lo agrega al PATH de esta sesion ----------
:find_ffmpeg
for /d %%P in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%V in ("%%P\ffmpeg-*") do (
        if exist "%%V\bin\ffmpeg.exe" set "PATH=%%V\bin;%PATH%"
    )
)
exit /b 0
