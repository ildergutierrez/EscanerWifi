# =======================================================
#  librerias.py — Instalador multiplataforma
#  Compatible con Windows y Linux (incluido Kali)
#  Auto-crea venv en Linux para evitar PEP 668
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
    "numpy"

]

# HERRAMIENTAS DEL SISTEMA para Linux (necesarias para escaneo de dispositivos)
LINUX_TOOLS = [
    "nmap",           # Para escaneo de red
    "net-tools",      # Para arp, netstat, route
    "iproute2",       # Para ip, ss (moderno)
    "arp-scan",       # Escaneo ARP avanzado (opcional)
    "speedtest-cli",
    ""
]

SO = platform.system()
ES_LINUX = SO == "Linux"
ES_WINDOWS = SO == "Windows"

# Ruta del entorno virtual (solo Linux)
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


def run_with_output(cmd):
    """Ejecuta comando y retorna output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"❌ Error ejecutando: {cmd}\n{e}")
        return ""


# -------------------------------------------------------
#  DETECTAR GESTOR DE PAQUETES LINUX
# -------------------------------------------------------
def detectar_gestor_paquetes():
    """Detecta el gestor de paquetes disponible en Linux"""
    gestores = {
        'apt': ['apt-get', 'apt'],
        'yum': ['yum'],
        'dnf': ['dnf'],
        'pacman': ['pacman'],
        'zypper': ['zypper'],
        'apk': ['apk']
    }
    
    for gestor, comandos in gestores.items():
        for comando in comandos:
            try:
                subprocess.run(['which', comando], capture_output=True, check=True)
                print(f"✅ Gestor detectado: {gestor} ({comando})")
                return gestor, comando
            except:
                continue
    
    print("⚠️  No se pudo detectar gestor de paquetes")
    return None, None


# -------------------------------------------------------
#  INSTALAR HERRAMIENTAS DEL SISTEMA (LINUX)
# -------------------------------------------------------

def instalar_herramientas_linux():
    """Instala herramientas del sistema necesarias para Linux"""
    if not ES_LINUX:
        return
    
    print("\n🔧 Verificando herramientas del sistema para Linux...")
    
    gestor, comando = detectar_gestor_paquetes()
    if not gestor:
        print("⚠️  No se pueden instalar herramientas del sistema")
        return
    
    # AGREGAR speedtest-cli A LAS HERRAMIENTAS A VERIFICAR
    herramientas_a_verificar = LINUX_TOOLS.copy()
    if "speedtest-cli" not in herramientas_a_verificar:
        herramientas_a_verificar.append("speedtest-cli")
    

    # Verificar herramientas ya instaladas
    herramientas_faltantes = []
    
    for herramienta in LINUX_TOOLS:
        print(f"  🔍 Verificando {herramienta}... ", end="")
        resultado = run_with_output(f"which {herramienta}")
        
        if resultado.strip():
            print("✅ Ya instalado")
        else:
            print("❌ Faltante")
            herramientas_faltantes.append(herramienta)
    
    if not herramientas_faltantes:
        print("\n✅ Todas las herramientas del sistema ya están instaladas")
        return
    
    print(f"\n📦 Instalando {len(herramientas_faltantes)} herramientas faltantes...\n")
    
    # Instalar según gestor de paquetes
    try:
        if gestor in ['apt', 'yum', 'dnf', 'apk']:
            # Actualizar repositorios primero
            print("🔄 Actualizando repositorios...\n")
            if gestor == 'apt':
                run(f"sudo {comando} update -y")
            elif gestor == 'yum' or gestor == 'dnf':
                run(f"sudo {comando} check-update -y")
            elif gestor == 'apk':
                run(f"sudo {comando} update")
            
            # Instalar herramientas
            for herramienta in herramientas_faltantes:
                print(f"  📥 Instalando {herramienta}...")
                if gestor == 'apt':
                    run(f"sudo {comando} install -y {herramienta}")
                elif gestor == 'yum' or gestor == 'dnf':
                    run(f"sudo {comando} install -y {herramienta}")
                elif gestor == 'apk':
                    run(f"sudo {comando} add {herramienta}")
        
        elif gestor == 'pacman':
            # Arch Linux / Manjaro
            run(f"sudo {comando} -Syu --noconfirm")
            for herramienta in herramientas_faltantes:
                print(f"  📥 Instalando {herramienta}...")
                run(f"sudo {comando} -S --noconfirm {herramienta}")
        
        elif gestor == 'zypper':
            # openSUSE
            run(f"sudo {comando} refresh")
            for herramienta in herramientas_faltantes:
                print(f"  📥 Instalando {herramienta}...")
                run(f"sudo {comando} install -y {herramienta}")
        
        print("\n✅ Herramientas del sistema instaladas correctamente")
        
    except Exception as e:
        print(f"❌ Error instalando herramientas del sistema: {e}")
        print("💡 Puedes instalarlas manualmente con:")
        if gestor == 'apt':
            print(f"  sudo apt install {' '.join(herramientas_faltantes)}")
        elif gestor == 'yum' or gestor == 'dnf':
            print(f"  sudo {gestor} install {' '.join(herramientas_faltantes)}")
        elif gestor == 'pacman':
            print(f"  sudo pacman -S {' '.join(herramientas_faltantes)}")


# -------------------------------------------------------
#  CREAR ENTORNO VIRTUAL AUTOMÁTICO (solo Linux)
# -------------------------------------------------------
def crear_venv_si_es_necesario():
    if ES_WINDOWS:
        return  # Windows usa pip normal

    # Linux/Kali
    if not os.path.exists(VENV_DIR):
        print("🟦 Creando entorno virtual (venv) requerido para Linux...")
        run("python3 -m venv venv")

    print(f"🟩 Usando entorno virtual: {VENV_DIR}")


# -------------------------------------------------------
#  VERIFICAR PERMISOS EN LINUX
# -------------------------------------------------------
def verificar_permisos_linux():
    """Verifica si el usuario tiene permisos para escanear red"""
    if not ES_LINUX:
        return
    
    print("\n🔐 Verificando permisos para escaneo de red...")
    
    # Verificar si es root
    if os.geteuid() == 0:
        print("✅ Ejecutando como root - Todos los permisos disponibles")
        return
    
    print("⚠️  No ejecutando como root. Algunas funciones pueden requerir sudo.")
    print("💡 Para mejor experiencia, ejecuta comandos de escaneo con sudo o como root")
    
    # Verificar si está en grupo sudo
    try:
        resultado = run_with_output("groups")
        if "sudo" in resultado or "wheel" in resultado:
            print("✅ Usuario en grupo sudo - Puede usar sudo para comandos")
        else:
            print("❌ Usuario no está en grupo sudo - Permisos limitados")
    except:
        pass


# -------------------------------------------------------
#  ACTUALIZAR PIP
# -------------------------------------------------------
def actualizar_pip(pip_path):
    print("⬆️  Actualizando pip y herramientas...")
    run(f"{pip_path} install --upgrade pip setuptools wheel")
    print("✅ pip actualizado con éxito.\n")


# -------------------------------------------------------
#  INSTALAR DEPENDENCIAS
# -------------------------------------------------------
def instalar_dependencias(pip_path):
    print("📦 Instalando dependencias necesarias...\n")

    for pkg in DEPENDENCIAS:
        print(f"🔸 Instalando {pkg} ...")
        run(f"{pip_path} install {pkg}")

    print("\n✅ Instalación completada.\n")


# -------------------------------------------------------
#  MENSAJE DE PYTHON
# -------------------------------------------------------
def mostrar_version_python(python_path):
    print("🐍 Versión de Python en uso:")
    run(f"{python_path} --version")
    print("ℹ️ Si quieres actualizar Python, ve a https://www.python.org/downloads/\n")


# -------------------------------------------------------
#  MOSTRAR INSTRUCCIONES DE USO
# -------------------------------------------------------
def mostrar_instrucciones():
    print("\n" + "="*60)
    print("📋 INSTRUCCIONES PARA USAR EL ESCANER")
    print("="*60)
    
    if ES_LINUX:
        print("\n💻 En Linux, para el mejor funcionamiento:")
        print("1. Ejecuta el escáner con permisos de root:")
        print("   sudo python3 main.py")
        print("\n2. O activa el entorno virtual y usa sudo:")
        print("   source venv/bin/activate")
        print("   sudo python main.py")
        print("\n3. Herramientas instaladas:")
        for herramienta in LINUX_TOOLS:
            print(f"   - {herramienta}")
    
    print("\n🔧 Comandos útiles:")
    print("   - Escanear red: sudo nmap -sn 192.168.1.0/24")
    print("   - Ver tabla ARP: ip neighbor show")
    print("   - Ver dispositivos: arp -a")
    
    print("\n" + "="*60)


# -------------------------------------------------------
#  FLUJO PRINCIPAL
# -------------------------------------------------------
def verificar_librerias():
    print("🚀 Iniciando verificación del entorno Escaner Wi-Fi 802.11...\n")

    if platform.system() == "Linux":
        activate_this = os.path.join("venv", "bin", "activate_this.py")
        if os.path.exists(activate_this):
            with open(activate_this) as f:
                exec(f.read(), {"__file__": activate_this})
            print("🔹 venv activado desde librerias.py")
        else:
            print("⚠️ No se encontró el venv. Ejecuta primero: python3 librerias.py")

    if ES_LINUX:
        # Instalar herramientas del sistema primero
        instalar_herramientas_linux()
        
        # Crear entorno virtual
        crear_venv_si_es_necesario()
        python = VENV_PY
        pip = VENV_PIP
        
        # Verificar permisos
        verificar_permisos_linux()
    else:
        python = sys.executable
        pip = f"{sys.executable} -m pip"

    actualizar_pip(pip)
    instalar_dependencias(pip)
    mostrar_version_python(python)
    
    mostrar_instrucciones()

    print("🎉 Entorno configurado correctamente en", SO)


# -------------------------------------------------------
#  EJECUCIÓN
# -------------------------------------------------------
if __name__ == "__main__":
    verificar_librerias()