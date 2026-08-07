from pathlib import Path


ML_ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = ML_ROOT / "artifacts"
DATASET_DIR = ML_ROOT / "datasets"
MODEL_PATH = ARTIFACT_DIR / "isolation_forest.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"
MODEL_VERSION = "isolation_forest_v1"
RANDOM_SEED = 42

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
DATASET_DIR.mkdir(parents=True, exist_ok=True)
