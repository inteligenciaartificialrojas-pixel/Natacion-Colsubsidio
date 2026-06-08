"""Inicialización del entorno de pruebas y configuración del path de importación."""
from __future__ import annotations
import os
import sys

# Agregar la carpeta 'code' al path de Python para que las pruebas importen sus módulos directamente
code_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../code"))
if code_path not in sys.path:
    sys.path.insert(0, code_path)
