#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scanner.py - NetGuard · Escáner de red profesional
Descubre hosts y puertos con clasificación de riesgo
"""

import nmap
import socket
import subprocess
import os
import re

class NetworkScanner:
    """
    Escáner de red profesional para descubrir dispositivos y puertos abiertos.
    Clasifica puertos con niveles: BAJO, MEDIO, ALTO, CRITICO.
    """
    
    # Base de conocimiento de puertos (alineada con IA)
    RISK_DATABASE = {
        21:    ("FTP",        "ALTO",    "FTP transmite credenciales en texto plano. Usar SFTP/FTPS."),
        22:    ("SSH",        "MEDIO",   "SSH seguro si está bien configurado. Usar autenticación por claves."),
        23:    ("Telnet",     "CRITICO", "TELNET - TRANSMITE TODO EN TEXTO PLANO. Deshabilitar INMEDIATAMENTE."),
        25:    ("SMTP",       "MEDIO",   "Servidor de correo. Configurar contra relay abierto."),
        53:    ("DNS",        "MEDIO",   "DNS. Asegurar contra amplificación y cache poisoning."),
        80:    ("HTTP",       "MEDIO",   "HTTP sin cifrar. Redirigir a HTTPS con HSTS."),
        110:   ("POP3",       "ALTO",    "POP3 sin cifrar. Usar POP3S (puerto 995)."),
        111:   ("RPC",        "ALTO",    "RPC bind. Superficie de ataque innecesaria."),
        135:   ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall perimetral."),
        137:   ("NetBIOS",    "ALTO",    "NetBIOS Name Service. Filtra información de red."),
        138:   ("NetBIOS",    "ALTO",    "NetBIOS Datagram. Deshabilitar si no es necesario."),
        139:   ("NetBIOS",    "ALTO",    "NetBIOS Session. Posible vector de SMB."),
        143:   ("IMAP",       "ALTO",    "IMAP sin cifrar. Usar IMAPS (puerto 993)."),
        443:   ("HTTPS",      "BAJO",    "HTTPS con cifrado. Verificar certificado válido."),
        445:   ("SMB",        "CRITICO", "SMB - VECTOR DE RANSOMWARE. Bloquear en firewall perimetral AHORA."),
        465:   ("SMTPS",      "BAJO",    "SMTP sobre SSL. Correcto."),
        514:   ("Syslog",     "MEDIO",   "Syslog. Información del sistema en texto plano."),
        587:   ("SMTP",       "MEDIO",   "SMTP con autenticación. Configurar correctamente."),
        593:   ("RPC",        "ALTO",    "RPC sobre HTTP. Superficie innecesaria."),
        631:   ("IPP",        "BAJO",    "Internet Printing Protocol. Deshabilitar si no se usa."),
        993:   ("IMAPS",      "BAJO",    "IMAP sobre SSL. Correcto."),
        995:   ("POP3S",      "BAJO",    "POP3 sobre SSL. Correcto."),
        1025:  ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall."),
        1026:  ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall."),
        1027:  ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall."),
        1028:  ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall."),
        1029:  ("MS-RPC",     "ALTO",    "Microsoft RPC. Bloquear en firewall."),
        1433:  ("MSSQL",      "ALTO",    "SQL Server expuesto. No exponer a internet."),
        1521:  ("Oracle",     "ALTO",    "Oracle DB expuesta. No exponer a internet."),
        1723:  ("PPTP",       "ALTO",    "PPTP inseguro. Usar OpenVPN o WireGuard."),
        2049:  ("NFS",        "ALTO",    "Network File System. Configurar exports correctamente."),
        3306:  ("MySQL",      "ALTO",    "MySQL/MariaDB expuesta. Bind a localhost en my.cnf."),
        3389:  ("RDP",        "CRITICO", "RDP - VECTOR #1 DE RANSOMWARE. Bloquear. Usar VPN."),
        5432:  ("PostgreSQL", "ALTO",    "PostgreSQL expuesta. Bind a localhost en postgresql.conf."),
        5900:  ("VNC",        "CRITICO", "VNC sin cifrar. Usar solo por túnel SSH/VPN."),
        5901:  ("VNC",        "CRITICO", "VNC sin cifrar. Usar solo por túnel SSH/VPN."),
        5985:  ("WinRM",      "ALTO",    "Windows Remote Management. Configurar con HTTPS."),
        5986:  ("WinRM",      "BAJO",    "WinRM sobre HTTPS. Correcto si está bien configurado."),
        6379:  ("Redis",      "CRITICO", "Redis - PERMITE ESCRIBIR ARCHIVOS. Bind a localhost YA."),
        8080:  ("HTTP-Alt",   "MEDIO",   "HTTP alternativo. Verificar aplicación."),
        8443:  ("HTTPS-Alt",  "BAJO",    "HTTPS alternativo. Verificar certificado."),
        9000:  ("SonarQube",  "MEDIO",   "SonarQube. Configurar con autenticación."),
        9090:  ("Prometheus", "MEDIO",   "Prometheus. Configurar autenticación."),
        9200:  ("Elastic",    "ALTO",    "Elasticsearch. Configurar autenticación YA."),
        9300:  ("Elastic",    "ALTO",    "Elasticsearch cluster."),
        11211: ("Memcached",  "ALTO",    "Memcached - RIESGO DE AMPLIFICACIÓN DDoS."),
        27017: ("MongoDB",    "CRITICO", "MongoDB - HISTÓRICAMENTE SIN AUTENTICACIÓN. Bind a localhost."),
        27018: ("MongoDB",    "CRITICO", "MongoDB sharded."),
        27019: ("MongoDB",    "CRITICO", "MongoDB config server."),
        28017: ("MongoDB",    "CRITICO", "MongoDB web status."),
    }
    
    # Combinaciones peligrosas de puertos
    DANGEROUS_COMBOS = [
        ({445, 3389}, "CRITICO", "SMB + RDP", "Combinación favorita de ransomware. Bloquear ambos."),
        ({23, 22}, "CRITICO", "Telnet + SSH", "Telnet activo junto a SSH. Eliminar Telnet."),
        ({3306, 80}, "ALTO", "MySQL + HTTP", "Web con BD expuesta. Bloquear MySQL en firewall."),
        ({3306, 443}, "ALTO", "MySQL + HTTPS", "Web con BD expuesta. Bloquear MySQL."),
        ({27017, 80}, "CRITICO", "MongoDB + HTTP", "MongoDB expuesto junto a web. Bind a localhost."),
        ({5900, 3389}, "CRITICO", "VNC + RDP", "Doble acceso remoto. Proteger con VPN."),
        ({6379, 22}, "CRITICO", "Redis + SSH", "Redis permite escribir claves SSH. Bind a localhost."),
        ({135, 445}, "CRITICO", "MS-RPC + SMB", "Stack Windows completo expuesto. Bloquear."),
    ]

    def __init__(self, output_callback=None):
        """
        Inicializa el escáner.
        Args:
            output_callback: Función para enviar mensajes a la UI
        """
        self.output_callback = output_callback
        self.scanner = None
        self._init_nmap()

    def _init_nmap(self):
        """Inicializa nmap de forma segura"""
        try:
            self.scanner = nmap.PortScanner()
            self._output("✅ Nmap inicializado correctamente")
        except Exception as e:
            self._output(f"❌ Error inicializando nmap: {e}")
            self._output("   Ejecuta: sudo apt install nmap")
            self.scanner = None

    def _output(self, message):
        """Envía mensaje a la UI o lo imprime en consola"""
        if self.output_callback:
            self.output_callback(message)
        else:
            print(message)

    def check_nmap(self):
        """Verifica si nmap está instalado y accesible"""
        try:
            result = subprocess.run(['which', 'nmap'], 
                                   capture_output=True, 
                                   text=True)
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, "nmap no encontrado"
        except Exception as e:
            return False, str(e)

    def get_local_ip(self):
        """Obtiene la IP local de la máquina"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def get_network_range(self):
        """Genera el rango de red en formato CIDR"""
        local_ip = self.get_local_ip()
        try:
            if local_ip.startswith("127."):
                return "127.0.0.1/32"
            parts = local_ip.split('.')
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        except Exception:
            return "192.168.1.0/24"

    def scan_hosts_sync(self):
        """
        Escanea la red local para encontrar dispositivos activos.
        Retorna lista de diccionarios con información de cada host.
        """
        # Verificar nmap
        nmap_ok, _ = self.check_nmap()
        if not nmap_ok or not self.scanner:
            self._output("❌ Nmap no está disponible")
            self._output("   Instala nmap: sudo apt install nmap")
            return []

        # Verificar permisos
        try:
            if os.geteuid() != 0:
                self._output("⚠ ADVERTENCIA: No se ejecuta como root")
                self._output("   Ejecuta: sudo python n_main.py")
        except Exception:
            pass

        network_range = self.get_network_range()
        devices = []

        try:
            self._output(f"🔍 Escaneando hosts en {network_range}...")
            self._output("   (puede tomar hasta 30 segundos)")

            # Escaneo rápido de hosts (-sn = ping scan)
            self.scanner.scan(hosts=network_range, arguments='-sn -T4')

            for host in self.scanner.all_hosts():
                # Obtener hostname
                hostname = "Desconocido"
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except Exception:
                    pass

                # Obtener MAC y vendor
                mac = "Desconocida"
                vendor = "Desconocido"
                try:
                    if 'mac' in self.scanner[host]['addresses']:
                        mac = self.scanner[host]['addresses']['mac']
                        if 'vendor' in self.scanner[host] and mac in self.scanner[host]['vendor']:
                            vendor = self.scanner[host]['vendor'][mac]
                except Exception:
                    pass

                devices.append({
                    "ip": host,
                    "hostname": hostname,
                    "mac": mac,
                    "vendor": vendor,
                    "status": self.scanner[host].state()
                })

                self._output(f"  ✅ Encontrado: {host} ({hostname}) - {vendor}")

            self._output(f"✅ Escaneo completado: {len(devices)} dispositivo(s)")

        except Exception as e:
            self._output(f"❌ Error en escaneo: {e}")

        return devices

    def scan_ports_sync(self, ip):
        """
        Escanea puertos abiertos en una IP específica.
        Retorna lista de puertos abiertos.
        """
        open_ports = []

        if not self.scanner:
            self._output(f"  ⚠ Escáner no disponible")
            return []

        try:
            self._output(f"  🔍 Escaneando puertos en {ip}...")
            # Escaneo rápido de puertos comunes (-F)
            self.scanner.scan(ip, arguments='-F -T4')

            if ip in self.scanner.all_hosts():
                for proto in self.scanner[ip].all_protocols():
                    for port in self.scanner[ip][proto].keys():
                        if self.scanner[ip][proto][port]['state'] == 'open':
                            open_ports.append(port)
                            self._output(f"     🔹 Puerto {port} abierto")

                if open_ports:
                    self._output(f"  ✅ {len(open_ports)} puerto(s) abierto(s) en {ip}")
                else:
                    self._output(f"  ℹ️ {ip}: Sin puertos abiertos")

        except Exception as e:
            self._output(f"  ⚠ Error escaneando {ip}: {e}")

        return open_ports

    def classify_ports(self, ports):
        """
        Clasifica puertos según nivel de riesgo.
        Retorna (lista_clasificada, puntuación_total)
        """
        results = []
        total_score = 0

        risk_scores = {
            "BAJO": 1,
            "MEDIO": 3,
            "ALTO": 6,
            "CRITICO": 10
        }

        for port in sorted(ports):
            if port in self.RISK_DATABASE:
                service, level, recommendation = self.RISK_DATABASE[port]
            else:
                service = f"Puerto {port}"
                level = "MEDIO"
                recommendation = f"Investigar qué servicio usa el puerto {port}"

            total_score += risk_scores.get(level, 3)

            results.append({
                "port": port,
                "service": service,
                "risk": level,
                "recommendation": recommendation
            })

        return results, total_score

    def find_dangerous_combinations(self, ports_set):
        """
        Detecta combinaciones peligrosas de puertos.
        Retorna lista de combinaciones encontradas.
        """
        found = []
        for combo_ports, severity, name, desc in self.DANGEROUS_COMBOS:
            if combo_ports.issubset(ports_set):
                found.append({
                    "ports": sorted(combo_ports),
                    "severity": severity,
                    "name": name,
                    "description": desc
                })
        return found