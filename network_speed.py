# network_speed.py
import speedtest
import json
from datetime import datetime

def test_network_speed():
    """
    Mide la velocidad de subida, bajada y ping del Internet actual.
    Devuelve un diccionario con resultados detallados.
    """
    try:
        st = speedtest.Speedtest()
        st.get_best_server()  # Selecciona el servidor más cercano automáticamente
        download_speed = st.download()
        upload_speed = st.upload()
        ping = st.results.ping

        # Convertir de bits/segundo a Megabits/segundo (Mbps)
        download_mbps = round(download_speed / 1_000_000, 2)
        upload_mbps = round(upload_speed / 1_000_000, 2)

        result = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "ping_ms": round(ping, 2),
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "message": "Medición completada con éxito"
        }
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": 999.0,
            "message": "Error durante la medición"
        }


if __name__ == "__main__":
    print("⏳ Midiendo velocidad de Internet...\n")
    result = test_network_speed()
    print(json.dumps(result, indent=2, ensure_ascii=False))
