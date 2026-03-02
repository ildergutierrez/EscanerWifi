import psutil
import time


class TrafficMonitor:

    def __init__(self):
        self.last_bytes_sent = 0
        self.last_bytes_recv = 0
        self.initialize()

    def initialize(self):
        net_io = psutil.net_io_counters()
        self.last_bytes_sent = net_io.bytes_sent
        self.last_bytes_recv = net_io.bytes_recv

    def get_traffic(self):
        net_io = psutil.net_io_counters()

        current_sent = net_io.bytes_sent
        current_recv = net_io.bytes_recv

        upload_speed = current_sent - self.last_bytes_sent
        download_speed = current_recv - self.last_bytes_recv

        self.last_bytes_sent = current_sent
        self.last_bytes_recv = current_recv

        return {
            "upload_kb": round(upload_speed / 1024, 2),
            "download_kb": round(download_speed / 1024, 2)
        }

    def evaluate_risk(self, upload_kb, download_kb):
        total = upload_kb + download_kb

        if total > 5000:
            return "ALTO"
        elif total > 1000:
            return "MEDIO"
        else:
            return "BAJO"