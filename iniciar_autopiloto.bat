@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Paradoja Infinita - autopiloto

echo ============================================
echo   PARADOJA INFINITA - autopiloto
echo ============================================

rem ---------- 1. Python y entorno virtual ----------
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: primero ejecuta iniciar.bat una vez para crear el entorno.
    goto :fail
)

rem ---------- 2. Dependencias (solo si cambiaron) ----------
set "STAMP=.venv\requirements.installed"
fc /b requirements.txt "%STAMP%" >nul 2>&1
if errorlevel 1 (
    echo [setup] Instalando dependencias de Python ...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
    copy /y requirements.txt "%STAMP%" >nul
)

rem ---------- 3. .env ----------
if not exist ".env" (
    echo ERROR: falta el archivo .env. Copia .env.example como .env y pon tu PAGE_ID y tu PAGE_ACCESS_TOKEN.
    goto :fail
)

rem ---------- 4. FFmpeg (el autopiloto genera Reels) ----------
where ffmpeg >nul 2>&1 && where ffprobe >nul 2>&1 && goto :have_ffmpeg
for /d %%P in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%V in ("%%P\ffmpeg-*") do (
        if exist "%%V\bin\ffmpeg.exe" set "PATH=%%V\bin;%PATH%"
    )
)
where ffmpeg >nul 2>&1 || (echo ERROR: FFmpeg no encontrado. Ejecuta iniciar.bat una vez para instalarlo. & goto :fail)

:have_ffmpeg
rem ---------- 5. Autopiloto (Ctrl+C o cerrar la ventana para detenerlo) ----------
echo.
echo Deja esta ventana abierta ^(minimizada^) y el PC encendido y sin suspender.
echo El registro queda en autopiloto.log
echo.
".venv\Scripts\python.exe" autopiloto.py %*
pause
exit /b %errorlevel%

:fail
echo.
pause
exit /b 1
