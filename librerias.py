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
librerias = {
    "PyQt6": "PyQt6",
    "scapy": "scapy",
    "requests": "requests",
    "psutil": "psutil",
    "mac_vendor_lookup": "mac-vendor-lookup",
    "pywifi":"pywifi",
    "ifaddr":"ifaddr",
    "urllib3": "urllib3",
    "certifi": "certifi",
    "chardet": "chardet",
    "idna": "idna",
    "colorama": "colorama",
    "setuptools": "setuptools",
    "wheel": "wheel",
    "future": "future",
    "speedtest-cli":"speedtest-cli",
    "qt-material": "qt-material"
}

def run_cmd(cmd):
    """Ejecuta un comando del sistema mostrando salida."""
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando: {cmd}\n{e}")


def actualizar_pip():
    """Actualiza pip y setuptools."""
    print("⬆️  Actualizando pip y setuptools...")
    run_cmd(f"{sys.executable} -m pip install --upgrade pip setuptools wheel")
    print("✅ pip actualizado correctamente.\n")


def desinstalar_todo():
    """Desinstala todas las librerías listadas."""
    print("🧹 Desinstalando librerías antiguas...\n")
    for modulo, paquete in librerias.items():
        nombre_pkg = paquete.split("==")[0]
        run_cmd(f"{sys.executable} -m pip uninstall -y {nombre_pkg}")
    print("\n✅ Desinstalación completa.\n")


def instalar_todo():
    """Reinstala todas las librerías requeridas."""
    print("📦 Instalando librerías necesarias...\n")
    for modulo, paquete in librerias.items():
        print(f"🔸 Instalando {paquete} ...")
        run_cmd(f"{sys.executable} -m pip install {paquete}")
    print("\n✅ Instalación completada correctamente.\n")


def actualizar_python():
    """Intenta actualizar Python (solo muestra guía si requiere instalador)."""
    print("🐍 Verificando versión de Python...\n")
    run_cmd("python --version")
    print("ℹ️  Para actualizar Python manualmente:")
    print("👉  Visita: https://www.python.org/downloads/")
    print("⚠️  La actualización automática desde pip no es segura.\n")


def verificar_librerias():
    """Ejecuta ciclo completo: actualizar pip, desinstalar e instalar todo."""
    print("🚀 Iniciando reinstalación completa del entorno CoffeeGrow...\n")
    actualizar_pip()
    #desinstalar_todo()
    instalar_todo()
    actualizar_python()
    print("🎉 Entorno CoffeeGrow actualizado y limpio.\n")


# Ejecutar verificación al inicio
if __name__ == "__main__":
    verificar_librerias()

