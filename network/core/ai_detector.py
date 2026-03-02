import numpy as np
from sklearn.ensemble import IsolationForest


class AnomalyDetector:

    def __init__(self):
        self.model = IsolationForest(contamination=0.1)
        self.training_data = []
        self.is_trained = False

    # -----------------------------
    # ENTRENAMIENTO INICIAL
    # -----------------------------
    def train(self, data):
        """
        data debe ser lista de [upload_kb, download_kb]
        """
        self.training_data = np.array(data)
        self.model.fit(self.training_data)
        self.is_trained = True

    # -----------------------------
    # PREDICCIÓN
    # -----------------------------
    def predict(self, upload_kb, download_kb):

        if not self.is_trained:
            return "MODELO_NO_ENTRENADO"

        sample = np.array([[upload_kb, download_kb]])
        prediction = self.model.predict(sample)

        if prediction[0] == -1:
            return "ANOMALIA"
        else:
            return "NORMAL"