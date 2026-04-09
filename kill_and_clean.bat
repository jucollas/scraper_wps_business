@echo off
REM Script para terminar procesos de Chrome y limpiar locks
REM SEGURO: No toca credenciales

setlocal enabledelayedexpansion

echo ============================================================
echo TERMINAR PROCESOS Y LIMPIAR CHROME
echo ============================================================
echo.

REM Paso 1: Terminar procesos
echo [PASO 1/3] Terminando procesos...
echo [LIMPIEZA] Terminando Chrome y ChromeDriver...

taskkill /F /IM chrome.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   terminado chrome.exe
) else (
    echo   - chrome.exe no en ejecucion
)

taskkill /F /IM chromedriver.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   terminado chromedriver.exe
) else (
    echo   - chromedriver.exe no en ejecucion
)

REM Esperar a que Windows libere los archivos
timeout /t 2 /nobreak >nul
echo.

REM Paso 2: Limpiar locks
echo [PASO 2/3] Limpiando archivos de lock...

if exist "wsp_session_chrome" (
    echo [LIMPIEZA] Limpiando locks en: wsp_session_chrome
    
    REM Eliminar archivos de lock individuales
    if exist "wsp_session_chrome\SingletonLock" (
        del /F /Q "wsp_session_chrome\SingletonLock" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado SingletonLock
    )
    
    if exist "wsp_session_chrome\SingletonCookie" (
        del /F /Q "wsp_session_chrome\SingletonCookie" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado SingletonCookie
    )
    
    if exist "wsp_session_chrome\SingletonSocket" (
        del /F /Q "wsp_session_chrome\SingletonSocket" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado SingletonSocket
    )
    
    if exist "wsp_session_chrome\lockfile" (
        del /F /Q "wsp_session_chrome\lockfile" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado lockfile
    )
    
    if exist "wsp_session_chrome\.parentlock" (
        del /F /Q "wsp_session_chrome\.parentlock" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado .parentlock
    )
    
    if exist "wsp_session_chrome\DevToolsActivePort" (
        del /F /Q "wsp_session_chrome\DevToolsActivePort" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado DevToolsActivePort
    )
    
    if exist "wsp_session_chrome\CrashpadMetrics-active.pma" (
        del /F /Q "wsp_session_chrome\CrashpadMetrics-active.pma" >nul 2>&1
        if %ERRORLEVEL% EQU 0 echo   terminado CrashpadMetrics-active.pma
    )
) else (
    echo - Perfil wsp_session_chrome no encontrado
)

echo.


pause
