@echo off
echo Creando ejecutable...
pyinstaller --onefile --windowed --name "Generador_Reportes" main.py
echo Ejecutable creado en dist/Generador_Reportes.exe
pause