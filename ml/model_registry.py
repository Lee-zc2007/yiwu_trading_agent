import json
from datetime import UTC, datetime
from threading import Lock

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from .config import METADATA_PATH, MODEL_PATH, MODEL_VERSION, RANDOM_SEED
from .feature_engineering import FEATURE_NAMES


class IsolationForestRegistry:
    def __init__(self):
        self._model = None
        self._metadata: dict = {}
        self._mtime: float | None = None
        self._lock = Lock()

    def train(self, rows: list[dict[str, float]], contamination: float = 0.08) -> dict:
        if len(rows) < 30:
            raise ValueError("训练 Isolation Forest 至少需要 30 条特征记录")
        matrix = np.asarray([[row[name] for name in FEATURE_NAMES] for row in rows], dtype=float)
        pipeline = Pipeline([
            ("scaler", RobustScaler()),
            ("model", IsolationForest(n_estimators=180, contamination=contamination, random_state=RANDOM_SEED, n_jobs=-1)),
        ])
        pipeline.fit(matrix)
        raw_scores = -pipeline.decision_function(matrix)
        low, high = float(np.percentile(raw_scores, 5)), float(np.percentile(raw_scores, 95))
        metadata = {
            "model_name": "IsolationForest",
            "model_version": MODEL_VERSION,
            "trained_at": datetime.now(UTC).isoformat(),
            "row_count": len(rows),
            "feature_names": FEATURE_NAMES,
            "random_seed": RANDOM_SEED,
            "contamination": contamination,
            "calibration_low": low,
            "calibration_high": high,
            "anomaly_rate": round(float((pipeline.predict(matrix) == -1).mean()), 4),
            "data_type": "reproducible_demo_transactions",
            "disclaimer": "模型仅用于辅助识别异常交易，不代表欺诈结论。",
        }
        joblib.dump(pipeline, MODEL_PATH)
        METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        with self._lock:
            self._model, self._metadata, self._mtime = pipeline, metadata, MODEL_PATH.stat().st_mtime
        return metadata

    def load(self):
        if not MODEL_PATH.exists() or not METADATA_PATH.exists():
            return None
        mtime = MODEL_PATH.stat().st_mtime
        with self._lock:
            if self._model is None or self._mtime != mtime:
                self._model = joblib.load(MODEL_PATH)
                self._metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
                self._mtime = mtime
        return self._model

    def predict_one(self, features: dict[str, float]) -> dict:
        model = self.load()
        if model is None:
            raise FileNotFoundError("Isolation Forest 模型尚未训练")
        matrix = np.asarray([[features[name] for name in FEATURE_NAMES]], dtype=float)
        raw = float(-model.decision_function(matrix)[0])
        low = float(self._metadata.get("calibration_low", -0.2)); high = float(self._metadata.get("calibration_high", 0.2))
        normalized = max(0.0, min(1.0, (raw - low) / max(high - low, 1e-6)))
        return {"anomaly_score": round(normalized, 4), "raw_score": round(raw, 6), "model_version": self._metadata.get("model_version", MODEL_VERSION), "model_status": "loaded"}

    def status(self) -> dict:
        if not MODEL_PATH.exists():
            return {"status": "missing", "model_version": MODEL_VERSION, "model_exists": False}
        self.load()
        return {"status": "ready", "model_exists": True, **self._metadata}

    def reload(self) -> bool:
        with self._lock:
            self._model = None; self._metadata = {}; self._mtime = None
        return self.load() is not None


model_registry = IsolationForestRegistry()
