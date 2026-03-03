#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor.py - NetGuard · Monitor de tráfico en tiempo real
"""

import psutil
import time

class TrafficMonitor:
    """
    Monitorea el tráfico de red en tiempo real.
    Calcula velocidades de subida y bajada.
    """

    def __init__(self):
        self.last_bytes_sent = 0
        self.last_bytes_recv = 0
        self.last_time = time.time()
        self.initialize()

    def initialize(self):
        """Inicializa los contadores de bytes"""
        try:
            net_io = psutil.net_io_counters()
            self.last_bytes_sent = net_io.bytes_sent
            self.last_bytes_recv = net_io.bytes_recv
            self.last_time = time.time()
        except Exception as e:
            print(f"❌ Error inicializando monitor: {e}")

    def get_traffic(self):
        """
        Calcula velocidad de subida/bajada desde última llamada.
        Retorna dict con upload_kb, download_kb, total_kb
        """
        try:
            net_io = psutil.net_io_counters()
            current_time = time.time()
            time_delta = current_time - self.last_time

            # Evitar división por cero
            if time_delta < 0.1:
                time_delta = 0.1

            current_sent = net_io.bytes_sent
            current_recv = net_io.bytes_recv

            upload_speed = (current_sent - self.last_bytes_sent) / time_delta
            download_speed = (current_recv - self.last_bytes_recv) / time_delta

            # Actualizar para próxima llamada
            self.last_bytes_sent = current_sent
            self.last_bytes_recv = current_recv
            self.last_time = current_time

            return {
                "upload_kb": round(upload_speed / 1024, 2),
                "download_kb": round(download_speed / 1024, 2),
                "total_kb": round((upload_speed + download_speed) / 1024, 2)
            }

        except Exception as e:
            print(f"❌ Error obteniendo tráfico: {e}")
            return {"upload_kb": 0.0, "download_kb": 0.0, "total_kb": 0.0}

    def evaluate_risk(self, upload_kb, download_kb):
        """
        Evalúa riesgo basado en volumen de tráfico.
        Retorna: "BAJO", "MEDIO", "ALTO"
        """
        total = upload_kb + download_kb

        if total > 5000:      # > 5 MB/s
            return "ALTO"
        elif total > 1000:     # 1-5 MB/s
            return "MEDIO"
        else:                   # < 1 MB/s
            return "BAJO"