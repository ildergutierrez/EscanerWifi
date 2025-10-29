# network_status.py
import subprocess
import platform
import re
import socket
import psutil
from typing import Dict, Optional, Tuple

def get_connected_wifi_info() -> Dict[str, Optional[str]]:
    """
    Obtiene información de la red WiFi a la que está conectado el dispositivo.
    """
    system = platform.system().lower()
    try:
        if system == "windows":
            return _get_windows_wifi_info()
        elif system == "darwin":
            return _get_macos_wifi_info()
        elif system == "linux":
            return _get_linux_wifi_info()
        else:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}
    except Exception as e:
        print(f"[network_status] Error: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}


def _get_windows_wifi_info() -> Dict[str, Optional[str]]:
    """Obtiene SSID, BSSID, señal e IP en Windows usando netsh"""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'],
            capture_output=True,
            text=True,
            encoding='cp850',  # ¡CRUCIAL PARA ESPAÑOL EN WINDOWS!
            errors='replace',
            timeout=10
        )

        if result.returncode != 0:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

        output = result.stdout

        # --- SSID ---
        ssid_match = re.search(r'SSID\s*:\s*(.+)', output, re.IGNORECASE)
        ssid = ssid_match.group(1).strip() if ssid_match else None
        if ssid and (ssid.lower() in ['<not associated>', 'none', ''] or 'BSSID' in ssid):
            ssid = None

        # --- BSSID ---
        bssid_match = re.search(r'BSSID\s*:\s*([0-9A-Fa-f:]{17})', output, re.IGNORECASE)
        bssid = bssid_match.group(1).upper() if bssid_match else None

        # --- Señal ---
        signal_match = re.search(r'Se.al\s*:\s*(\d+)%', output, re.IGNORECASE)
        if not signal_match:
            signal_match = re.search(r'Signal\s*:\s*(\d+)%', output, re.IGNORECASE)
        signal_percent = signal_match.group(1) if signal_match else None
        signal_dbm = f"-{100 - int(signal_percent)}" if signal_percent else None

        # --- IP ---
        ip_address = _get_local_ip_address()

        connected = bool(ssid and ip_address)

        return {
            'connected': connected,
            'ssid': ssid if connected else None,
            'bssid': bssid if connected else None,
            'signal': signal_dbm if connected else None,
            'ip_address': ip_address if connected else None
        }

    except Exception as e:
        print(f"[Windows WiFi] Error: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}


def _get_macos_wifi_info() -> Dict[str, Optional[str]]:
    """Obtiene información WiFi en macOS"""
    try:
        result = subprocess.run(
            ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

        output = result.stdout

        ssid_match = re.search(r'\s+SSID:\s+(.+)', output)
        ssid = ssid_match.group(1).strip() if ssid_match else None

        bssid_match = re.search(r'\s+BSSID:\s+([0-9a-f:]{17})', output)
        bssid = bssid_match.group(1).upper() if bssid_match else None

        signal_match = re.search(r'agrCtlRSSI:\s*(-?\d+)', output)
        signal = signal_match.group(1) if signal_match else None

        connected = ssid is not None and ssid != ""

        ip_address = _get_local_ip_address() if connected else None

        return {
            'connected': connected,
            'ssid': ssid if connected else None,
            'bssid': bssid if connected else None,
            'signal': signal if connected else None,
            'ip_address': ip_address
        }

    except Exception as e:
        print(f"[macOS WiFi] Error: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}


def _get_linux_wifi_info() -> Dict[str, Optional[str]]:
    """Obtiene información WiFi en Linux (nmcli o iwconfig)"""
    try:
        # --- nmcli ---
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'ACTIVE,SSID,BSSID,SIGNAL', 'dev', 'wifi'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.startswith('yes'):
                    parts = line.split(':')
                    if len(parts) >= 4:
                        ssid = parts[1] if parts[1] else None
                        bssid = parts[2].upper() if parts[2] else None
                        signal_percent = parts[3] if parts[3] else None
                        signal_dbm = f"-{100 - int(signal_percent)}" if signal_percent else None
                        ip_address = _get_local_ip_address()
                        return {
                            'connected': True,
                            'ssid': ssid,
                            'bssid': bssid,
                            'signal': signal_dbm,
                            'ip_address': ip_address
                        }

        # --- iwconfig fallback ---
        result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            ssid = bssid = signal = None
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    m = re.search(r'ESSID:"([^"]+)"', line)
                    if m:
                        ssid = m.group(1)
                if 'Access Point:' in line:
                    m = re.search(r'Access Point:\s+([0-9A-Fa-f:]{17})', line)
                    if m:
                        bssid = m.group(1).upper()
                if 'Signal level' in line:
                    m = re.search(r'Signal level=(-?\d+)', line)
                    if m:
                        signal = m.group(1)

            connected = ssid is not None and ssid != ""
            ip_address = _get_local_ip_address() if connected else None

            return {
                'connected': connected,
                'ssid': ssid if connected else None,
                'bssid': bssid if connected else None,
                'signal': signal if connected else None,
                'ip_address': ip_address
            }

        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

    except Exception as e:
        print(f"[Linux WiFi] Error: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}


def _get_local_ip_address() -> Optional[str]:
    """Obtiene la IP local (WiFi o Ethernet)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                        return addr.address
        except:
            pass
    return None


def _get_default_gateway() -> Optional[str]:
    """Obtiene el gateway por defecto en Windows/Linux de forma más robusta"""
    try:
        system = platform.system().lower()
        if system == "windows":
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="replace",
                timeout=10
            )
            output = result.stdout.lower()

            # 🧩 Buscar línea con "0.0.0.0" y una IP válida al final
            for line in output.splitlines():
                if "0.0.0.0" in line and re.search(r"\d+\.\d+\.\d+\.\d+", line):
                    m = re.findall(r"(\d+\.\d+\.\d+\.\d+)", line)
                    if len(m) >= 2:
                        gateway_ip = m[1]
                        if gateway_ip != "0.0.0.0":
                            return gateway_ip
        else:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=10
            )
            m = re.search(r"default via ([\d.]+)", result.stdout)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"[Gateway] Error detectando gateway: {e}")
        pass

    # Valor por defecto de respaldo
    return "192.168.1.254"


def is_connected_to_network(target_ssid: str, target_bssid: str = None) -> bool:
    """
    Verifica si estamos conectados a la red especificada.
    Maneja espacios, tildes, codificación y BSSID.
    """
    if not target_ssid:
        return False

    wifi = get_connected_wifi_info()
    if not wifi['connected'] or not wifi['ssid']:
        return False

    # LIMPIEZA PROFUNDA
    current_ssid = wifi['ssid']
    if current_ssid:
        current_ssid = re.sub(r'[\r\n\t]', '', current_ssid).strip()
        current_ssid = re.sub(r'\s+', ' ', current_ssid)  # Espacios múltiples

    target_clean = re.sub(r'[\r\n\t]', '', target_ssid).strip()
    target_clean = re.sub(r'\s+', ' ', target_clean)

    # Comparación insensible a mayúsculas/minúsculas
    if current_ssid.lower() != target_clean.lower():
        return False

    # BSSID (opcional, más confiable)
    if target_bssid and wifi['bssid']:
        c = re.sub(r'[^0-9A-F]', '', wifi['bssid'].upper())
        t = re.sub(r'[^0-9A-F]', '', target_bssid.upper())
        return c == t

    return True

def get_network_congestion(interface: str = None) -> Dict[str, float]:
    """Analiza estabilidad, latencia, pérdida y señal"""
    try:
        wifi_info = get_connected_wifi_info()
        if not wifi_info['connected']:
            return {
                'stability_percentage': 0.0,
                'packet_loss': 100.0,
                'latency': 999.0,
                'signal_quality': 0.0
            }

        signal_quality = _calculate_signal_quality(wifi_info.get('signal'))
        latency, packet_loss = _measure_network_metrics()
        stability = _calculate_stability(signal_quality, packet_loss, latency)

        return {
            'stability_percentage': stability,
            'packet_loss': packet_loss,
            'latency': latency,
            'signal_quality': signal_quality
        }

    except Exception as e:
        print(f"[Congestión] Error: {e}")
        return {
            'stability_percentage': 0.0,
            'packet_loss': 100.0,
            'latency': 999.0,
            'signal_quality': 0.0
        }


def _calculate_signal_quality(signal_dbm: Optional[str]) -> float:
    try:
        if not signal_dbm:
            return 50.0
        dbm = float(signal_dbm)
        if dbm >= -30: return 100.0
        if dbm >= -50: return 90.0
        if dbm >= -60: return 80.0
        if dbm >= -67: return 70.0
        if dbm >= -70: return 60.0
        if dbm >= -80: return 40.0
        if dbm >= -90: return 20.0
        return 10.0
    except:
        return 50.0


def _measure_network_metrics() -> Tuple[float, float]:
    """Mide latencia y pérdida de paquetes hacia el gateway."""
    try:
        gateway = _get_default_gateway()
        if not gateway:
            return 999.0, 100.0

        count = 3
        timeout = 2
        system = platform.system().lower()
        if system == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), gateway]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), gateway]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        output = result.stdout

        print("\n=== DEBUG SALIDA PING ===\n")
        print(output)
        print("=========================\n")

        # --- WINDOWS ---
        if system == "windows":
            # porcentaje de pérdida
            loss_match = re.search(r"(\d+)%\s*perdidos", output, re.IGNORECASE)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0

            # tiempo promedio
            time_match = re.search(r"media\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
            latency = float(time_match.group(1)) if time_match else 999.0

        # --- LINUX / MAC ---
        else:
            loss_match = re.search(r"(\d+)% packet loss", output)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0

            time_match = re.search(r"= [\d.]+/([\d.]+)/", output)
            latency = float(time_match.group(1)) if time_match else 999.0

        return latency, packet_loss

    except Exception as e:
        print(f"[Ping] Error midiendo métricas: {e}")
        return 999.0, 100.0


def _calculate_stability(signal_quality: float, packet_loss: float, latency: float) -> float:
    signal_score = signal_quality
    loss_score = max(0, 100 - packet_loss)
    latency_score = max(0, 100 - (latency / 10))
    return max(0, min(100, (
        signal_score * 0.4 +
        loss_score * 0.4 +
        latency_score * 0.2
    )))


def is_current_network(ssid: str, bssid: str = None) -> bool:
    """Alias para is_connected_to_network"""
    return is_connected_to_network(ssid, bssid)

# === FUNCIÓN CLAVE: get_current_network_info ===
def get_current_network_info() -> Dict[str, Optional[str]]:
    """
    Devuelve información de la red actualmente conectada.
    Alias de get_connected_wifi_info para compatibilidad con ap_device_scanner.
    """
    return get_connected_wifi_info()
# === PRUEBA RÁPIDA ===
if __name__ == "__main__":
    print("Detectando WiFi...")
    info = get_connected_wifi_info()
    print(f"Conectado: {info['connected']}")
    print(f"SSID: {info['ssid']}")
    print(f"BSSID: {info['bssid']}")
    print(f"Señal: {info['signal']} dBm")
    print(f"IP: {info['ip_address']}")

    if info['connected']:
        print("\nCongestión:")
        c = get_network_congestion()
        print(f"Estabilidad: {c['stability_percentage']:.1f}%")
        print(f"Pérdida: {c['packet_loss']:.1f}%")
        print(f"Latencia: {c['latency']:.1f} ms")
        print(f"Señal: {c['signal_quality']:.1f}%")

        print(f"\n¿Conectado a red actual?: {is_connected_to_network(info['ssid'])}")