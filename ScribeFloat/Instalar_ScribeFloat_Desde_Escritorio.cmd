@echo off
setlocal
chcp 65001 >nul
set "SCRIPT=%~dp0Instalar_ScribeFloat_Python.ps1"
set "LOG=%USERPROFILE%\Desktop\Whisper_Solution_instalacion.log"
echo Instalando Whisper Solution... > "%LOG%"
echo Script: %SCRIPT% >> "%LOG%"
echo. >> "%LOG%"
if not exist "%SCRIPT%" (
    echo ERROR: No se encontro el script de instalacion: "%SCRIPT%"
    echo ERROR: No se encontro el script de instalacion: "%SCRIPT%" >> "%LOG%"
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" >> "%LOG%" 2>&1
set "INSTALL_EXIT=%ERRORLEVEL%"
type "%LOG%"
echo.
if not "%INSTALL_EXIT%"=="0" (
    echo ERROR: No se pudo instalar Whisper Solution.
    echo Revise el log: "%LOG%"
    pause
    exit /b %INSTALL_EXIT%
)
echo OK: Whisper Solution quedo instalado.
echo Acceso directo: "%USERPROFILE%\Desktop\Whisper Solution.lnk"
echo Log: "%LOG%"
pause
