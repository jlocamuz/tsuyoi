import PyInstaller.__main__
import sys
import os

# Configuración para el build
PyInstaller.__main__.run([
    '--onefile',           # Un solo archivo .exe
    '--windowed',          # Sin ventana de consola
    '--name=Generador_Reportes_Asistencia',
    '--distpath=dist',     # Carpeta de salida
    '--workpath=build',    # Carpeta temporal
    '--specpath=.',        # Archivo .spec
    '--clean',             # Limpiar cache
    'main.py'
])