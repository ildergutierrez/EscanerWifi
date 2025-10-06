# # Instalar todas las dependencias necesarias

# pip install requests scapy psutil PyQt6 mac-vendor-lookup

# # O instalar una por una:

# pip install requests                # Para consultas HTTP a APIs
# pip install scapy                   # Para manipulación y escaneo de paquetes/red (scapy)
# pip install psutil                  # Para obtener información del sistema (CPU, red, procesos)
# pip install PyQt6                   # Para la interfaz gráfica (widgets, señales, etc.)
# pip install mac-vendor-lookup       # Para identificar fabricantes por dirección MAC

# # Sugerencia:

# # - Recomiendo usar un entorno virtual (venv) antes de instalar:

# # python -m venv venv

# # source venv/bin/activate   (Linux/macOS)  o  venv\Scripts\activate (Windows)

# # - Si tu sistema usa python3 por separado, usa `pip3` en lugar de `pip`.


import importlib
import subprocess
import sys

# Lista de librerías requeridas
REQUIRED_LIBRARIES = {
    "PyQt6": "PyQt6",
    "scapy": "scapy",
    "requests": "requests",
    "psutil": "psutil",
    "mac_vendor_lookup": "mac-vendor-lookup"
}

def verificar_librerias():
    for lib in REQUIRED_LIBRARIES:
        try:
            importlib.import_module(lib)
            print(f"✔ La librería '{lib}' ya está instalada.")
        except ImportError:
            print(f"⚠ La librería '{lib}' no está instalada. Instalando...")
            instalar_libreria(lib)

def instalar_libreria(lib):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
        print(f"✅ Librería '{lib}' instalada correctamente.")
    except Exception as e:
        print(f"❌ No se pudo instalar la librería '{lib}'. Error: {e}")

# Ejecutar verificación al inicio
if __name__ == "__main__":
    verificar_librerias()

