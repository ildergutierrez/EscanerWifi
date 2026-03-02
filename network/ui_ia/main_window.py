from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QTextEdit, QLabel
)
from PyQt6.QtCore import Qt, QTimer

from core.scanner import NetworkScanner
from core.monitor import TrafficMonitor
from core.ai_detector import AnomalyDetector


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sistema Inteligente de Seguridad en Red")
        self.setGeometry(100, 100, 900, 600)

        # =============================
        # INSTANCIAS DE MÓDULOS
        # =============================
        self.scanner = NetworkScanner()
        self.monitor = TrafficMonitor()
        self.ai_detector = AnomalyDetector()

        self.traffic_history = []

        # =============================
        # CONFIGURACIÓN UI
        # =============================
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.label = QLabel("Sistema Inteligente de Seguridad de Red")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)

        # Botones
        self.scan_button = QPushButton("Ejecutar Análisis de Vulnerabilidad")
        self.monitor_button = QPushButton("Iniciar Monitoreo en Tiempo Real")
        self.train_ai_button = QPushButton("Entrenar IA")

        # Agregar al layout
        layout.addWidget(self.label)
        layout.addWidget(self.output_area)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.monitor_button)
        layout.addWidget(self.train_ai_button)

        central_widget.setLayout(layout)

        # =============================
        # CONEXIONES
        # =============================
        self.scan_button.clicked.connect(self.run_scan)
        self.monitor_button.clicked.connect(self.start_monitoring)
        self.train_ai_button.clicked.connect(self.train_ai)

        # Timer para monitoreo
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_traffic)

    # =========================================================
    # FASE 2 – ANÁLISIS DE VULNERABILIDAD
    # =========================================================
    def run_scan(self):

        self.output_area.clear()
        self.output_area.append("🔎 Iniciando análisis de red...\n")

        devices = self.scanner.scan_hosts()

        if not devices:
            self.output_area.append("No se encontraron dispositivos activos.\n")
            return

        for device in devices:

            self.output_area.append(f"\nDispositivo: {device['ip']}")
            self.output_area.append(f"Estado: {device['status']}")

            ports = self.scanner.scan_ports(device['ip'])

            if not ports:
                self.output_area.append("✔ Sin puertos abiertos detectados.\n")
                continue

            classified, score = self.scanner.classify_ports(ports)

            self.output_area.append(f"Puertos abiertos: {ports}")
            self.output_area.append("Evaluación de riesgo:")

            for item in classified:
                self.output_area.append(
                    f"  - Puerto {item['port']} ({item['service']}) "
                    f"=> Riesgo: {item['risk']}"
                )
                self.output_area.append(
                    f"     Recomendación: {item['recommendation']}"
                )

            self.output_area.append(f"Puntaje total de riesgo: {score}")

            if score >= 8:
                self.output_area.append("🔴 Nivel de vulnerabilidad: ALTO\n")
            elif score >= 4:
                self.output_area.append("🟠 Nivel de vulnerabilidad: MEDIO\n")
            else:
                self.output_area.append("🟢 Nivel de vulnerabilidad: BAJO\n")

    # =========================================================
    # FASE 3 – MONITOREO EN TIEMPO REAL
    # =========================================================
    def start_monitoring(self):
        self.output_area.append("\n📡 Monitoreo en tiempo real iniciado...\n")
        self.timer.start(2000)  # cada 2 segundos

    def update_traffic(self):

        traffic = self.monitor.get_traffic()

        upload = traffic["upload_kb"]
        download = traffic["download_kb"]

        base_risk = self.monitor.evaluate_risk(upload, download)

        self.output_area.append(
            f"⬆ {upload} KB | ⬇ {download} KB | Riesgo base: {base_risk}"
        )

        # Guardamos historial para IA
        self.traffic_history.append([upload, download])

        # =====================================================
        # FASE 4 – DETECCIÓN DE ANOMALÍAS CON IA
        # =====================================================
        if self.ai_detector.is_trained:

            result = self.ai_detector.predict(upload, download)

            if result == "ANOMALIA":
                self.output_area.append("🧠 🔴 IA detectó ANOMALÍA en el tráfico\n")
            else:
                self.output_area.append("🧠 🟢 Tráfico normal según IA\n")

        else:
            self.output_area.append("🧠 IA aún no entrenada\n")

        if base_risk == "ALTO":
            self.output_area.append("⚠ Posible actividad sospechosa detectada\n")

    # =========================================================
    # ENTRENAMIENTO DEL MODELO IA
    # =========================================================
    def train_ai(self):

        if len(self.traffic_history) < 10:
            self.output_area.append(
                "⚠ Se necesitan al menos 10 muestras para entrenar la IA\n"
            )
            return

        self.ai_detector.train(self.traffic_history)

        self.output_area.append(
            "🧠 Modelo de IA entrenado correctamente\n"
        )