#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n_main.py  –  NetGuard · Punto de entrada principal
"""

import sys
import os
'''
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

# Verificar librerias (el modulo librerias.py vive en el paquete principal)
try:
    from backend.librerias import verificar_librerias
    verificar_librerias()
    print("Librerias verificadas correctamente")
except ImportError:
    # Si librerias.py no esta disponible aun (ejecucion directa de este modulo)
    pass
except Exception as e:
    print(f"Aviso al verificar librerias: {e}")'''

print("Iniciando NetGuard - Sistema de Seguridad de Red con IA Local...")
print("-" * 55)

from PyQt6.QtWidgets import QApplication
from ui_ia.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()