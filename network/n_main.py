#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetGuard - Sistema Inteligente de Seguridad en Red
Punto de entrada principal
"""

import sys
import os

# Obtener la ruta del directorio padre
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

# Verificar librerías
try:
    from librerias import verificar_librerias
    verificar_librerias()
    print("✅ Librerías verificadas correctamente")
except Exception as e:
    print(f"⚠ Error verificando librerías: {e}")

print("🚀 Iniciando NetGuard - Sistema de Seguridad de Red...")
print("   Presiona Ctrl+C para salir")
print("-" * 50)

from PyQt6.QtWidgets import QApplication
from ui_ia.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()