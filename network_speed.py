# network_speed.py
import json
from datetime import datetime
import socket
import platform
import sys
import os
import time
import subprocess

# ==============================================
# DETECCIÓN DE ENTORNO
# ==============================================
SYSTEM = platform.system().lower()
IS_LINUX = SYSTEM == "linux"
IS_WINDOWS = SYSTEM == "windows"

def test_network_speed():
    """
    Mide la velocidad de internet.
    Funciona con speedtest-cli (comando) o módulo speedtest.
    """
    print("🔍 Verificando conexión a internet...")
    
    # Verificar conexión primero
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        print("✅ Conectado a internet")
    except:
        return {
            "success": False,
            "error": "Sin conexión",
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": 999.0,
            "message": "No hay conexión a internet"
        }
    
    print("⏳ Iniciando test de velocidad...")
    
    # MÉTODO 1: Usar speedtest-cli (comando del sistema) - PRIMERA OPCIÓN
    try:
        print("📡 Intentando con speedtest-cli (comando)...")
        # Usar --simple para output legible
        result = subprocess.run(
            ['speedtest-cli', '--simple', '--secure'],
            capture_output=True,
            text=True,
            timeout=60  # 60 segundos máximo
        )
        
        if result.returncode == 0:
            output = result.stdout
            print("✅ speedtest-cli funcionó correctamente")
            
            # Parsear resultados
            ping = download = upload = 0
            for line in output.strip().split('\n'):
                if 'Ping:' in line:
                    try:
                        ping = float(line.split()[1])
                    except:
                        ping = 0
                elif 'Download:' in line:
                    try:
                        download = float(line.split()[1])
                    except:
                        download = 0
                elif 'Upload:' in line:
                    try:
                        upload = float(line.split()[1])
                    except:
                        upload = 0
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "ping_ms": round(ping, 1),
                "download_mbps": round(download, 2),
                "upload_mbps": round(upload, 2),
                "method": "speedtest-cli_command",
                "message": "Test completado con speedtest-cli"
            }
        else:
            print(f"⚠️  speedtest-cli falló: {result.stderr}")
    except FileNotFoundError:
        print("❌ speedtest-cli no encontrado como comando")
    except subprocess.TimeoutExpired:
        print("⏰ Timeout: speedtest-cli tardó demasiado")
    except Exception as e:
        print(f"⚠️  Error con speedtest-cli: {e}")
    
    # MÉTODO 2: Usar módulo Python speedtest (si está instalado)
    try:
        print("📡 Intentando con módulo speedtest...")
        import speedtest
        
        st = speedtest.Speedtest()
        st.get_best_server(timeout=10)
        
        print("📥 Midiendo descarga...")
        download = st.download()
        
        print("📤 Midiendo subida...")
        upload = st.upload()
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "ping_ms": round(st.results.ping, 1),
            "download_mbps": round(download / 1_000_000, 2),
            "upload_mbps": round(upload / 1_000_000, 2),
            "method": "speedtest_python",
            "message": "Test completado con módulo speedtest"
        }
    except ImportError:
        print("❌ Módulo speedtest no disponible")
    except Exception as e:
        print(f"❌ Error con módulo speedtest: {e}")
    
    # MÉTODO 3: Test rápido de ping como último recurso
    print("⚡ Usando método rápido (ping)...")
    try:
        # Test de ping a servidores confiables
        servers = [
            ("Google DNS", "8.8.8.8"),
            ("Cloudflare", "1.1.1.1"),
            ("Google", "google.com")
        ]
        
        pings = []
        for name, server in servers:
            try:
                start = time.time()
                socket.create_connection((server, 80), timeout=3)
                end = time.time()
                ping_ms = round((end - start) * 1000, 1)
                pings.append(ping_ms)
                print(f"   {name}: {ping_ms} ms")
            except:
                continue
        
        if not pings:
            raise Exception("No se pudo conectar a ningún servidor")
        
        avg_ping = round(sum(pings) / len(pings), 1)
        
        # Estimación muy básica basada en ping
        if avg_ping < 30:
            download_mbps = 50
            upload_mbps = 10
        elif avg_ping < 100:
            download_mbps = 20
            upload_mbps = 5
        else:
            download_mbps = 5
            upload_mbps = 1
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "ping_ms": avg_ping,
            "download_mbps": round(download_mbps, 2),
            "upload_mbps": round(upload_mbps, 2),
            "method": "ping_estimation",
            "message": "Estimación basada en ping"
        }
        
    except Exception as e:
        print(f"❌ Error en método rápido: {e}")
        return {
            "success": False,
            "error": str(e),
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": 999.0,
            "message": "Todos los métodos fallaron"
        }

# ==============================================
# EJECUCIÓN PRINCIPAL
# ==============================================
'''if __name__ == "__main__":
    print("=" * 50)
    print("🚀 TEST DE VELOCIDAD DE INTERNET")
    print("=" * 50)
    
    # Verificar qué está disponible
    print("🔍 Verificando herramientas disponibles...")
    
    # Verificar speedtest-cli como comando
    try:
        result = subprocess.run(['which', 'speedtest-cli'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ speedtest-cli (comando) disponible")
        else:
            print("❌ speedtest-cli (comando) NO disponible")
    except:
        print("❌ No se pudo verificar speedtest-cli")
    
    # Verificar módulo Python
    try:
        import speedtest
        print("✅ Módulo speedtest disponible")
    except ImportError:
        print("❌ Módulo speedtest NO disponible")
    
    print("-" * 50)
    
    # Ejecutar test
    result = test_network_speed()
    
    print("\n" + "=" * 50)
    print("📊 RESULTADOS")
    print("=" * 50)
    
    if result["success"]:
        print(f"✅ Ping: {result['ping_ms']} ms")
        print(f"📥 Descarga: {result['download_mbps']} Mbps")
        print(f"📤 Subida: {result['upload_mbps']} Mbps")
        print(f"🔧 Método usado: {result.get('method', 'desconocido')}")
        print(f"💬 {result.get('message', '')}")
    else:
        print(f"❌ Error: {result.get('message', 'Desconocido')}")
        
        # Instrucciones de instalación
        print("\n💡 SOLUCIÓN - Instala speedtest-cli:")
        if IS_LINUX:
            print("   1. Como comando del sistema:")
            print("      sudo apt install speedtest-cli")
            print("   2. Como módulo Python:")
            print("      pip install speedtest-cli")
            print("   3. O ejecuta el instalador completo:")
            print("      python3 librerias.py")
        else:
            print("   1. Como módulo Python:")
            print("      pip install speedtest-cli")
            print("   2. O ejecuta el instalador:")
            print("      python librerias.py")
    
    print("=" * 50)'''