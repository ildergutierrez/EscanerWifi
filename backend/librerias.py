# =======================================================
#  librerias.py — Instalador multiplataforma PROFESIONAL
#  Compatible con Windows y Linux (incluido Kali)
#  Manejo correcto de venv + permisos root automáticos
# =======================================================

import subprocess
import sys
import platform
import os

# -------------------------------------------------------
#  LIBRERÍAS REQUERIDAS
# -------------------------------------------------------
DEPENDENCIAS = [
    "PyQt6",
    "scapy",
    "requests",
    "psutil",
    "mac-vendor-lookup",
    "pywifi",
    "ifaddr",
    "urllib3",
    "certifi",
    "chardet",
    "idna",
    "colorama",
    "setuptools",
    "wheel",
    "future",
    "speedtest-cli",
    "qt-material",
    "python-dotenv",
    "python-nmap",
    "netifaces",
    "scikit-learn",
    "pandas",
    "matplotlib",
    "numpy",
    "scikit-learn numpy",
    "pdfplumber", "PyMuPDF", "reportlab", "fpdf", "weasyprint", 
    "pypdf", "PyPDF2", "python-docx"
]

LINUX_TOOLS = [
    "nmap",
    "net-tools",
    "iproute2",
    "arp-scan"
]

SO = platform.system()
ES_LINUX = SO == "Linux"
ES_WINDOWS = SO == "Windows"

VENV_DIR = "venv"
VENV_PY = os.path.join(VENV_DIR, "bin", "python")
VENV_PIP = os.path.join(VENV_DIR, "bin", "pip")

# -------------------------------------------------------
#  EJECUTAR COMANDOS
# -------------------------------------------------------
def run(cmd):
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando: {cmd}\n{e}")

def run_output(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

# -------------------------------------------------------
#  VERIFICAR PERMISOS ROOT (LINUX)
# -------------------------------------------------------
def verificar_permisos_root():
    if not ES_LINUX:
        return

    if os.geteuid() != 0:
        print("\n🔐 Se requieren permisos de administrador para ejecutar el escáner.")
        print("🔄 Reiniciando automáticamente con sudo...\n")

        python_exec = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = " ".join(sys.argv[1:])

        os.execvp("sudo", ["sudo", python_exec, script] + sys.argv[1:])

# -------------------------------------------------------
#  DETECTAR GESTOR DE PAQUETES
# -------------------------------------------------------
def detectar_gestor():
    gestores = ["apt", "dnf", "yum", "pacman", "zypper", "apk"]
    for gestor in gestores:
        if run_output(f"which {gestor}"):
            return gestor
    return None

# -------------------------------------------------------
#  INSTALAR HERRAMIENTAS LINUX
# -------------------------------------------------------
def instalar_herramientas_linux():
    if not ES_LINUX:
        return

    print("\n🔧 Verificando herramientas del sistema...")

    gestor = detectar_gestor()
    if not gestor:
        print("⚠️ No se detectó gestor de paquetes.")
        return

    faltantes = []
    for tool in LINUX_TOOLS:
        if run_output(f"which {tool}"):
            print(f"  ✅ {tool} ya está instalado")
        else:
            print(f"  ❌ {tool} faltante")
            faltantes.append(tool)

    if not faltantes:
        print("✅ Todas las herramientas del sistema están instaladas")
        return

    print("\n📦 Instalando herramientas faltantes...\n")

    if gestor == "apt":
        run("sudo apt update")
        run(f"sudo apt install -y {' '.join(faltantes)}")
    elif gestor in ["dnf", "yum"]:
        run(f"sudo {gestor} install -y {' '.join(faltantes)}")
    elif gestor == "pacman":
        run("sudo pacman -Syu --noconfirm")
        run(f"sudo pacman -S --noconfirm {' '.join(faltantes)}")
    elif gestor == "zypper":
        run("sudo zypper refresh")
        run(f"sudo zypper install -y {' '.join(faltantes)}")
    elif gestor == "apk":
        run("sudo apk update")
        run(f"sudo apk add {' '.join(faltantes)}")

    print("✅ Herramientas del sistema instaladas")

# -------------------------------------------------------
#  CREAR VENV
# -------------------------------------------------------
def crear_venv():
    if ES_WINDOWS:
        return

    if not os.path.exists(VENV_DIR):
        print("🟦 Creando entorno virtual...")
        run("python3 -m venv venv")
    else:
        print("🟩 Entorno virtual ya existe")

# -------------------------------------------------------
#  ACTUALIZAR PIP
# -------------------------------------------------------
def actualizar_pip(pip_path):
    run(f"{pip_path} install --upgrade pip setuptools wheel")

# -------------------------------------------------------
#  VERIFICAR PAQUETE
# -------------------------------------------------------
def paquete_instalado(python_path, paquete):
    try:
        subprocess.check_output(
            [python_path, "-m", "pip", "show", paquete],
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False

# -------------------------------------------------------
#  INSTALAR DEPENDENCIAS
# -------------------------------------------------------
def instalar_dependencias(python_path, pip_path):
    print("\n📦 Verificando dependencias...\n")

    for pkg in DEPENDENCIAS:
        if paquete_instalado(python_path, pkg):
            print(f"  ✅ {pkg} ya está instalado")
        else:
            print(f"  📥 Instalando {pkg}...")
            run(f"{pip_path} install {pkg}")

    print("\n✅ Dependencias verificadas correctamente")

# -------------------------------------------------------
#  FLUJO PRINCIPAL
# -------------------------------------------------------
def verificar_librerias():
    print("🚀 Iniciando configuración del entorno...\n")

    if ES_LINUX:
        verificar_permisos_root()  # 🔥 AQUÍ se asegura el permiso
        instalar_herramientas_linux()
        crear_venv()
        python = VENV_PY
        pip = VENV_PIP
    else:
        python = sys.executable
        pip = f"{sys.executable} -m pip"

    actualizar_pip(pip)
    instalar_dependencias(python, pip)

    print("\n🐍 Python en uso:")
    run(f"{python} --version")

    print("\n🎉 Entorno configurado correctamente en", SO)

# -------------------------------------------------------
#  EJECUCIÓN
# -------------------------------------------------------
if __name__ == "__main__":
    verificar_librerias()