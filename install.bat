@echo off
chcp 65001 >nul
title WBS Order Manager - Instalador

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       WBS Order Manager - Instalador     ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python no está instalado o no está en el PATH.
    echo  Descárgalo desde: https://www.python.org/downloads/
    echo  Asegúrate de marcar "Add Python to PATH" al instalar.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [OK] Python %PY_VER% encontrado.
echo.

:: Crear entorno virtual si no existe
if not exist ".venv\" (
    echo  [1/4] Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo  [OK] Entorno virtual creado.
) else (
    echo  [1/4] Entorno virtual ya existe, omitiendo.
)
echo.

:: Activar entorno virtual
echo  [2/4] Activando entorno virtual...
call .venv\Scripts\activate.bat
echo  [OK] Entorno virtual activado.
echo.

:: Actualizar pip
echo  [3/4] Actualizando pip...
python -m pip install --upgrade pip --quiet
echo  [OK] pip actualizado.
echo.

:: Instalar dependencias
echo  [4/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Fallo al instalar dependencias.
    pause
    exit /b 1
)
echo  [OK] Dependencias instaladas.
echo.

:: Crear acceso directo en el escritorio
echo  Creando acceso directo en el escritorio...
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\WBS Order Manager.bat
echo @echo off > "%SHORTCUT%"
echo cd /d "%SCRIPT_DIR%" >> "%SHORTCUT%"
echo call .venv\Scripts\activate.bat >> "%SHORTCUT%"
echo python app\main.py >> "%SHORTCUT%"
echo  [OK] Acceso directo creado: %SHORTCUT%
echo.

echo  ╔══════════════════════════════════════════╗
echo  ║   Instalacion completada exitosamente!   ║
echo  ║                                          ║
echo  ║  Ejecuta con:                            ║
echo  ║    "WBS Order Manager.bat" (escritorio)  ║
echo  ║  o desde aqui con:                       ║
echo  ║    run.bat                               ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Crear run.bat para ejecución rápida
echo @echo off > run.bat
echo cd /d "%~dp0" >> run.bat
echo call .venv\Scripts\activate.bat >> run.bat
echo python app\main.py >> run.bat
echo  [OK] run.bat creado.
echo.

set /p LAUNCH="¿Deseas iniciar la aplicación ahora? (s/n): "
if /i "%LAUNCH%"=="s" (
    echo  Iniciando WBS Order Manager...
    start "" python app\main.py
)

pause
