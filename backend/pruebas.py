# En tu código principal
from ap_device_scanner import *

network_info = get_current_network_info()
result = get_connected_devices(network_info)
print(json.dumps(result, indent=2, ensure_ascii=False))