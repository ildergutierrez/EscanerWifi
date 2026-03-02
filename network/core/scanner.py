import nmap
import socket


class NetworkScanner:

    def __init__(self):
        self.scanner = nmap.PortScanner()

        # Base de datos básica de riesgo por puerto
        self.risk_database = {
            21: ("FTP", "MEDIO", "Servicio sin cifrado. Se recomienda usar SFTP."),
            22: ("SSH", "BAJO", "Seguro si está bien configurado."),
            23: ("Telnet", "ALTO", "Transmite datos sin cifrado. Debe deshabilitarse."),
            80: ("HTTP", "MEDIO", "No cifrado. Se recomienda HTTPS."),
            443: ("HTTPS", "BAJO", "Comunicación cifrada segura."),
            3389: ("RDP", "ALTO", "Acceso remoto. Riesgo si está expuesto."),
        }

    # ----------------------------------
    # OBTENER IP LOCAL
    # ----------------------------------
    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        return local_ip

    # ----------------------------------
    # GENERAR RANGO
    # ----------------------------------
    def get_network_range(self):
        local_ip = self.get_local_ip()
        base_ip = ".".join(local_ip.split(".")[:-1])
        return f"{base_ip}.0/24"

    # ----------------------------------
    # ESCANEO DE HOSTS
    # ----------------------------------
    def scan_hosts(self):
        network_range = self.get_network_range()
        self.scanner.scan(hosts=network_range, arguments='-sn')

        devices = []

        for host in self.scanner.all_hosts():
            devices.append({
                "ip": host,
                "status": self.scanner[host].state()
            })

        return devices

    # ----------------------------------
    # ESCANEO DE PUERTOS
    # ----------------------------------
    def scan_ports(self, ip):
        self.scanner.scan(ip, arguments='-F')

        open_ports = []

        if ip in self.scanner.all_hosts():
            for proto in self.scanner[ip].all_protocols():
                ports = self.scanner[ip][proto].keys()
                for port in ports:
                    if self.scanner[ip][proto][port]['state'] == 'open':
                        open_ports.append(port)

        return open_ports

    # ----------------------------------
    # CLASIFICACIÓN DE RIESGO
    # ----------------------------------
    def classify_ports(self, ports):
        results = []
        total_score = 0

        risk_score = {
            "BAJO": 1,
            "MEDIO": 3,
            "ALTO": 5
        }

        for port in ports:
            if port in self.risk_database:
                service, level, recommendation = self.risk_database[port]
            else:
                service = "Desconocido"
                level = "MEDIO"
                recommendation = "Revisar servicio manualmente."

            total_score += risk_score[level]

            results.append({
                "port": port,
                "service": service,
                "risk": level,
                "recommendation": recommendation
            })

        return results, total_score