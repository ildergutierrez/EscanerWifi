#!/usr/bin/env python3
# diagnostico.py

import subprocess
import sys
import os

print("=" * 60)
print("🔍 DIAGNÓSTICO DEL SISTEMA DE ESCANEO")
print("=" * 60)

# 1. Verificar Python
print(f"\n📌 Python version: {sys.version}")
print(f"📌 Ejecutando como: {'root' if os.geteuid() == 0 else 'usuario normal'}")

# 2. Verificar nmap
print("\n📌 Verificando nmap:")
try:
    result = sub.run(['which', 'nmap'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✅ nmap encontrado en: {result.stdout.strip()}")
        
        # Ver versión
        version = sub.run(['nmap', '--version'], capture_output=True, text=True)
        print(f"   📋 Versión: {version.stdout.split()[2]}")
    else:
        print("   ❌ nmap NO está instalado")
        print("   📦 Instalar: sudo apt install nmap")
except Exception as e:
    print(f"   ❌ Error verificando nmap: {e}")

# 3. Probar escaneo simple
print("\n📌 Probando escaneo simple:")
try:
    # Escanear localhost
    result = sub.run(['nmap', '-sn', '127.0.0.1'], capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✅ nmap puede escanear localhost")
    else:
        print("   ❌ Error escaneando localhost")
        print(f"   Error: {result.stderr}")
except Exception as e:
    print(f"   ❌ Error ejecutando nmap: {e}")

# 4. Obtener IP local
print("\n📌 Obteniendo IP local:")
try:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    print(f"   ✅ IP local: {local_ip}")
    
    # Generar rango
    ip_parts = local_ip.split('.')
    network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
    print(f"   📡 Rango de red: {network}")
except Exception as e:
    print(f"   ❌ Error obteniendo IP: {e}")

# 5. Probar escaneo real
print("\n📌 Probando escaneo real (puede tomar 10 segundos):")
try:
    cmd = ['sudo', 'nmap', '-sn', '-T4', '--max-retries', '1', local_ip + '/24']
    print(f"   Ejecutando: {' '.join(cmd)}")
    
    result = sub.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        # Contar hosts encontrados
        lines = result.stdout.split('\n')
        hosts = [l for l in lines if 'Nmap scan report for' in l]
        print(f"   ✅ Escaneo exitoso. Encontrados {len(hosts)} hosts")
        for host in hosts[:5]:  # Mostrar primeros 5
            print(f"      {host}")
    else:
        print(f"   ❌ Error en escaneo")
        print(f"   Error: {result.stderr}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("🔧 RECOMENDACIONES:")
print("=" * 60)
print("1. Si nmap no está instalado: sudo apt install nmap")
print("2. Ejecutar siempre con: sudo python n_main.py")
print("3. Verificar que no haya firewall bloqueando: sudo ufw status")
print("4. Si todo falla, usar el método alternativo (ping)")