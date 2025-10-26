# En tu código principal
from mac_capacidad import get_router_info

# Para cada red detectada
red_info = {
    "BSSID": "C0:C9:E3:12:34:56",
    "Tecnologia": "WiFi 5 (AC)",
    "Fabricante": "TP-Link"  # Obtenido de vendor_lookup
}

router_data = get_router_info(
    red_info["BSSID"], 
    red_info["Tecnologia"],
    red_info["Fabricante"]
)

print(f"📡 Router: {router_data['model']}")
print(f"📊 Capacidad: {router_data['max_devices']} dispositivos")