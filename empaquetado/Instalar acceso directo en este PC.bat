@echo off
rem Copia Anonimizador.exe a este PC y crea un acceso directo en el Escritorio.
rem No necesita permisos de administrador. Despues se puede retirar la USB.
setlocal
set "DESTINO=%LOCALAPPDATA%\AnonimizadorLocal"
if not exist "%~dp0Anonimizador.exe" (
  echo No encuentro Anonimizador.exe junto a este archivo.
  pause & exit /b 1
)
if not exist "%DESTINO%" mkdir "%DESTINO%"
copy /y "%~dp0Anonimizador.exe" "%DESTINO%\Anonimizador.exe" >nul || (echo No se pudo copiar el programa. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Anonimizador.lnk');" ^
  "$s.TargetPath='%DESTINO%\Anonimizador.exe'; $s.WorkingDirectory='%DESTINO%';" ^
  "$s.IconLocation='%DESTINO%\Anonimizador.exe,0'; $s.Description='Anonimizador local de documentos'; $s.Save()" ^
  || (echo No se pudo crear el acceso directo. & pause & exit /b 1)
echo.
echo Listo. En el Escritorio quedo el icono "Anonimizador".
echo Ya puedes retirar la USB.
pause
