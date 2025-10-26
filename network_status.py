import subprocess
import platform
import re
import time
import socket
import psutil
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

def get_connected_wifi_info() -> Dict[str, Optional[str]]:
    """
    Obtiene información de la red WiFi a la que está conectado el dispositivo.
    
    Returns:
        Dict con:
        - 'connected': bool - Si está conectado a WiFi
        - 'ssid': str - Nombre de la red conectada (None si no está conectado)
        - 'bssid': str - Dirección MAC del AP (None si no está conectado)
        - 'signal': str - Intensidad de señal en dBm (None si no está conectado)
        - 'ip_address': str - Dirección IP local (None si no está conectado)
    """
    system = platform.system().lower()
    
    try:
        if system == "windows":
            return _get_windows_wifi_info()
        elif system == "darwin":  # macOS
            return _get_macos_wifi_info()
        elif system == "linux":
            return _get_linux_wifi_info()
        else:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}
    except Exception as e:
        print(f"Error detectando WiFi: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}


def is_connected_to_network(target_ssid: str, target_bssid: str = None) -> bool:
    """
    Verifica si el dispositivo está conectado a una red WiFi específica.
    
    Args:
        target_ssid: SSID de la red a verificar
        target_bssid: BSSID de la red a verificar (opcional, para mayor precisión)
    
    Returns:
        bool: True si está conectado a la red especificada
    """
    if not target_ssid:
        return False
        
    current_wifi = get_connected_wifi_info()
    
    if not current_wifi['connected'] or not current_wifi['ssid']:
        return False
    
    # Debug information
    print(f"🔍 Comparando redes:")
    print(f"   Target SSID: '{target_ssid}'")
    print(f"   Current SSID: '{current_wifi['ssid']}'")
    print(f"   Target BSSID: '{target_bssid}'")
    print(f"   Current BSSID: '{current_wifi['bssid']}'")
    
    # Comparar SSID (case insensitive y limpiar espacios)
    current_ssid_clean = current_wifi['ssid'].strip().lower()
    target_ssid_clean = target_ssid.strip().lower()
    
    print(f"   SSID comparación: '{current_ssid_clean}' vs '{target_ssid_clean}'")
    
    ssid_match = current_ssid_clean == target_ssid_clean
    
    if ssid_match:
        # Si se proporciona BSSID, verificar también para mayor precisión
        if target_bssid and current_wifi['bssid']:
            current_bssid_clean = current_wifi['bssid'].upper().replace('-', ':')
            target_bssid_clean = target_bssid.upper().replace('-', ':')
            
            print(f"   BSSID comparación: '{current_bssid_clean}' vs '{target_bssid_clean}'")
            
            bssid_match = current_bssid_clean == target_bssid_clean
            print(f"   Resultado final: SSID match + BSSID match = {bssid_match}")
            return bssid_match
        else:
            print(f"   Resultado final: SSID match (sin verificación BSSID) = True")
            return True
    
    print(f"   Resultado final: No match = False")
    return False


def get_current_network_info() -> Dict[str, Optional[str]]:
    """
    Obtiene información detallada de la red actualmente conectada.
    
    Returns:
        Dict con información completa de la red conectada
    """
    wifi_info = get_connected_wifi_info()
    
    if not wifi_info['connected']:
        return wifi_info
    
    # Obtener información adicional de red
    try:
        # Obtener gateway y máscara de subred
        gateways = psutil.net_if_addrs()
        for interface, addrs in gateways.items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address == wifi_info.get('ip_address'):
                    wifi_info['subnet_mask'] = addr.netmask
                    break
        
        # Obtener gateway por defecto
        default_gateway = _get_default_gateway()
        wifi_info['gateway'] = default_gateway
        
    except Exception as e:
        print(f"Error obteniendo información adicional de red: {e}")
    
    return wifi_info

def _get_windows_wifi_info() -> Dict[str, Optional[str]]:
    """Obtener información WiFi en Windows"""
    try:
        # Usar netsh para obtener información WiFi
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode != 0:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}
        
        output = result.stdout
        
        # Buscar SSID
        ssid_match = re.search(r'SSID\s*:\s*(.+)', output)
        ssid = ssid_match.group(1).strip() if ssid_match else None
        
        # Buscar BSSID
        bssid_match = re.search(r'BSSID\s*:\s*([0-9A-Fa-f:]{17})', output)
        bssid = bssid_match.group(1).upper() if bssid_match else None
        
        # Buscar señal
        signal_match = re.search(r'Señal\s*:\s*(\d+)%', output)
        if not signal_match:
            signal_match = re.search(r'Signal\s*:\s*(\d+)%', output)
        
        signal_percent = signal_match.group(1) if signal_match else None
        signal_dbm = f"-{100 - int(signal_percent)}" if signal_percent else None
        
        connected = ssid is not None and ssid != "" and ssid.lower() != "none"
        
        # Obtener dirección IP
        ip_address = _get_local_ip_address()
        
        return {
            'connected': connected,
            'ssid': ssid if connected else None,
            'bssid': bssid if connected else None,
            'signal': signal_dbm if connected else None,
            'ip_address': ip_address if connected else None
        }
        
    except Exception as e:
        print(f"Error en Windows WiFi: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

def _get_macos_wifi_info() -> Dict[str, Optional[str]]:
    """Obtener información WiFi en macOS"""
    try:
        # Obtener SSID
        ssid_result = subprocess.run(
            ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
            capture_output=True, 
            text=True
        )
        
        if ssid_result.returncode != 0:
            return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}
        
        output = ssid_result.stdout
        
        # Buscar SSID
        ssid_match = re.search(r'SSID:\s*(.+)', output)
        ssid = ssid_match.group(1).strip() if ssid_match else None
        
        # Buscar BSSID
        bssid_match = re.search(r'BSSID:\s*([0-9A-Fa-f:]{17})', output)
        bssid = bssid_match.group(1).upper() if bssid_match else None
        
        # Buscar señal
        signal_match = re.search(r'agrCtlRSSI:\s*(-?\d+)', output)
        signal = signal_match.group(1) if signal_match else None
        
        connected = ssid is not None and ssid != ""
        
        # Obtener dirección IP
        ip_address = _get_local_ip_address()
        
        return {
            'connected': connected,
            'ssid': ssid if connected else None,
            'bssid': bssid if connected else None,
            'signal': signal if connected else None,
            'ip_address': ip_address if connected else None
        }
        
    except Exception as e:
        print(f"Error en macOS WiFi: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

def _get_linux_wifi_info() -> Dict[str, Optional[str]]:
    """Obtener información WiFi en Linux"""
    try:
        # Intentar con nmcli (NetworkManager)
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'ACTIVE,SSID,BSSID,SIGNAL', 'dev', 'wifi'],
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith('si'):  # Conexión activa
                    parts = line.split(':')
                    if len(parts) >= 4:
                        ssid = parts[1] if parts[1] != "" else None
                        bssid = parts[2].upper() if parts[2] != "" else None
                        signal_percent = parts[3] if parts[3] else None
                        signal_dbm = f"-{100 - int(signal_percent)}" if signal_percent else None
                        
                        # Obtener dirección IP
                        ip_address = _get_local_ip_address()
                        
                        return {
                            'connected': True,
                            'ssid': ssid,
                            'bssid': bssid,
                            'signal': signal_dbm,
                            'ip_address': ip_address
                        }
        
        # Fallback: usar iwconfig
        result = subprocess.run(['iwconfig'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            ssid = None
            bssid = None
            signal = None
            
            for line in lines:
                ssid_match = re.search(r'ESSID:"([^"]+)"', line)
                if ssid_match:
                    ssid = ssid_match.group(1)
                
                bssid_match = re.search(r'Access Point:\s*([0-9A-Fa-f:]{17})', line)
                if bssid_match:
                    bssid = bssid_match.group(1).upper()
                
                signal_match = re.search(r'Signal level=(-?\d+)', line)
                if signal_match:
                    signal = signal_match.group(1)
            
            connected = ssid is not None and ssid != ""
            
            # Obtener dirección IP
            ip_address = _get_local_ip_address() if connected else None
            
            return {
                'connected': connected,
                'ssid': ssid if connected else None,
                'bssid': bssid if connected else None,
                'signal': signal if connected else None,
                'ip_address': ip_address if connected else None
            }
        
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}
        
    except Exception as e:
        print(f"Error en Linux WiFi: {e}")
        return {'connected': False, 'ssid': None, 'bssid': None, 'signal': None, 'ip_address': None}

def _get_local_ip_address() -> Optional[str]:
    """Obtener la dirección IP local del dispositivo"""
    try:
        # Crear socket temporal para obtener IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # No necesita estar conectado realmente
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            # Fallback: usar psutil
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                        return addr.address
        except Exception:
            pass
    return None

def _get_default_gateway() -> Optional[str]:
    """Obtener la dirección del gateway por defecto"""
    try:
        # Usar psutil para obtener información de red
        gateways = psutil.net_if_addrs()
        for interface, addrs in gateways.items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    # Obtener gateway desde la configuración de red
                    try:
                        if platform.system().lower() == "windows":
                            result = subprocess.run(
                                ['route', 'print', '0.0.0.0'],
                                capture_output=True, 
                                text=True
                            )
                            if result.returncode == 0:
                                match = re.search(r'0\.0\.0\.0\s+0\.0\.0\.0\s+([\d.]+)', result.stdout)
                                if match:
                                    return match.group(1)
                        else:
                            result = subprocess.run(
                                ['ip', 'route', 'show', 'default'],
                                capture_output=True, 
                                text=True
                            )
                            if result.returncode == 0:
                                match = re.search(r'default via ([\d.]+)', result.stdout)
                                if match:
                                    return match.group(1)
                    except:
                        pass
        
        # Fallback: gateway común
        return "192.168.1.1"  # Gateway común como fallback
        
    except Exception:
        return "192.168.1.1"

def get_network_congestion(interface: str = None) -> Dict[str, float]:
    """
    Analiza la congestión de la red WiFi conectada.
    
    Args:
        interface: Nombre de la interfaz de red (opcional)
    
    Returns:
        Dict con métricas de congestión:
        - 'stability_percentage': float - Porcentaje de estabilidad (0-100)
        - 'packet_loss': float - Porcentaje de pérdida de paquetes
        - 'latency': float - Latencia en ms
        - 'signal_quality': float - Calidad de señal (0-100)
    """
    try:
        # Obtener información de conexión
        wifi_info = get_connected_wifi_info()
        
        if not wifi_info['connected']:
            return {
                'stability_percentage': 0.0,
                'packet_loss': 100.0,
                'latency': 999.0,
                'signal_quality': 0.0
            }
        
        # Métricas de señal
        signal_quality = _calculate_signal_quality(wifi_info.get('signal'))
        
        # Métricas de red (ping a gateway)
        latency, packet_loss = _measure_network_metrics()
        
        # Calcular estabilidad general (ponderado)
        stability = _calculate_stability(signal_quality, packet_loss, latency)
        
        return {
            'stability_percentage': stability,
            'packet_loss': packet_loss,
            'latency': latency,
            'signal_quality': signal_quality
        }
        
    except Exception as e:
        print(f"Error analizando congestión: {e}")
        return {
            'stability_percentage': 0.0,
            'packet_loss': 100.0,
            'latency': 999.0,
            'signal_quality': 0.0
        }

def _calculate_signal_quality(signal_dbm: Optional[str]) -> float:
    """Calcular calidad de señal basada en dBm"""
    try:
        if not signal_dbm:
            return 0.0
            
        dbm = float(signal_dbm)
        
        # Escala de calidad de señal (dBm a porcentaje)
        if dbm >= -30: return 100.0
        if dbm >= -50: return 90.0
        if dbm >= -60: return 80.0
        if dbm >= -67: return 70.0
        if dbm >= -70: return 60.0
        if dbm >= -80: return 40.0
        if dbm >= -90: return 20.0
        return 10.0
        
    except Exception:
        return 0.0

def _measure_network_metrics() -> Tuple[float, float]:
    """Medir latencia y pérdida de paquetes"""
    try:
        # Intentar ping al gateway por defecto
        gateway = _get_default_gateway()
        if not gateway:
            return 999.0, 100.0
        
        # Ejecutar ping (2 intentos, timeout 2 segundos)
        count = 2
        timeout = 2
        
        if platform.system().lower() == "windows":
            cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), gateway]
        else:
            cmd = ['ping', '-c', str(count), '-W', str(timeout), gateway]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = result.stdout
        
        # Analizar resultado del ping
        if platform.system().lower() == "windows":
            # Windows
            loss_match = re.search(r'\((\d+)%', output)
            time_match = re.search(r'= (\d+)ms', output)
        else:
            # Linux/macOS
            loss_match = re.search(r'(\d+)% packet loss', output)
            time_match = re.search(r'min/avg/max/[^=]*= [\d.]+/([\d.]+)', output)
        
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0
        latency = float(time_match.group(1)) if time_match else 999.0
        
        return latency, packet_loss
        
    except Exception:
        return 999.0, 100.0

def _calculate_stability(signal_quality: float, packet_loss: float, latency: float) -> float:
    """Calcular porcentaje de estabilidad general"""
    # Ponderaciones
    signal_weight = 0.4
    loss_weight = 0.4
    latency_weight = 0.2
    
    # Normalizar métricas
    signal_score = signal_quality
    loss_score = max(0, 100 - packet_loss)  # Invertir pérdida
    latency_score = max(0, 100 - (latency / 10))  # Penalizar latencia alta
    
    # Calcular estabilidad ponderada
    stability = (
        signal_score * signal_weight +
        loss_score * loss_weight +
        latency_score * latency_weight
    )
    
    return max(0, min(100, stability))

# Función de conveniencia para verificar si es la red conectada
def is_current_network(ssid: str, bssid: str = None) -> bool:
    """
    Verifica si la red especificada es la red actualmente conectada.
    
    Args:
        ssid: SSID de la red a verificar
        bssid: BSSID de la red a verificar (opcional, para mayor precisión)
    
    Returns:
        bool: True si es la red conectada actualmente
    """
    return is_connected_to_network(ssid, bssid)

# Prueba del módulo
if __name__ == "__main__":
    print("🔍 Detectando conexión WiFi...")
    wifi_info = get_connected_wifi_info()
    print(f"Conectado: {wifi_info['connected']}")
    print(f"SSID: {wifi_info['ssid']}")
    print(f"BSSID: {wifi_info['bssid']}")
    print(f"Señal: {wifi_info['signal']} dBm")
    print(f"IP: {wifi_info['ip_address']}")
    
    if wifi_info['connected']:
        print("\n📊 Analizando congestión de red...")
        congestion = get_network_congestion()
        print(f"Estabilidad: {congestion['stability_percentage']:.1f}%")
        print(f"Pérdida de paquetes: {congestion['packet_loss']:.1f}%")
        print(f"Latencia: {congestion['latency']:.1f} ms")
        print(f"Calidad de señal: {congestion['signal_quality']:.1f}%")
        
        # Probar función de verificación específica
        print(f"\n🔗 Conectado a esta red específica: {is_connected_to_network(wifi_info['ssid'], wifi_info['bssid'])}")    