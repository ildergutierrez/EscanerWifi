import sys
import os

# Obtener la ruta del directorio padre (Scaner/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)
from librerias import verificar_librerias
verificar_librerias()
print("finalizo")
from PyQt6.QtWidgets import QApplication
from ui_ia.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()