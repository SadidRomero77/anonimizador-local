@echo off
rem Genera la carpeta USB\ con Anonimizador.exe listo para copiar a una memoria.
rem Requiere Python 3.9+ solo en el PC donde se empaqueta (no en los PC donde se usa).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || goto :error
)
.venv\Scripts\python -m pip install --quiet --upgrade pymupdf pyinstaller pillow || goto :error
.venv\Scripts\python prueba.py >nul || goto :error
.venv\Scripts\python prueba_pdf.py >nul || goto :error
.venv\Scripts\python empaquetado\crear_icono.py || goto :error
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name Anonimizador ^
  --icon "%~dp0empaquetado\icono.ico" --distpath "%~dp0empaquetado\dist" --workpath "%~dp0empaquetado\build" ^
  --specpath "%~dp0empaquetado" --exclude-module tkinter --exclude-module PIL app.py || goto :error
if not exist USB mkdir USB
copy /y empaquetado\dist\Anonimizador.exe USB\ >nul || (
  echo.
  echo ERROR: no pude reemplazar USB\Anonimizador.exe porque la app esta abierta.
  echo Cierrala con su boton "Cerrar la app" y vuelve a ejecutar empaquetar.bat.
  exit /b 1
)
copy /y "empaquetado\Instalar acceso directo en este PC.bat" USB\ >nul
copy /y empaquetado\LEEME_USB.txt USB\LEEME.txt >nul
echo.
echo Listo: copia la carpeta USB a la memoria.
goto :eof
:error
echo.
echo ERROR: el empaquetado fallo. Revisa los mensajes de arriba.
exit /b 1
