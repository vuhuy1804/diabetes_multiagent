"""A tiny TensorFlow integration smoke test using SYNTHETIC rows only.

Creates artifacts under models/keras_dlk1_smoke and outputs/keras_dlk1_smoke.
These synthetic results must never be reported as medical/academic performance.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from training.keras_dlk1 import train_keras_experiment  # noqa: E402


def main():
    rng = np.random.default_rng(2026)
    rows = []
    for i in range(320):
        rows.append({
            "gender": "Female" if i % 2 == 0 else "Male",
            "age": float(rng.integers(18, 80)),
            "hypertension": int(i % 5 == 0),
            "heart_disease": int(i % 7 == 0),
            "smoking_history": "former" if i % 3 == 0 else "never",
            "bmi": round(float(rng.uniform(18, 39)), 2),
            "HbA1c_level": round(float(rng.uniform(4, 9)), 2),
            "blood_glucose_level": int(rng.integers(80, 240)),
            "diabetes": int(i % 5 == 0),  # synthetic label; not medical
        })
    with tempfile.TemporaryDirectory() as temp:
        csv = Path(temp) / "synthetic_only.csv"
        pd.DataFrame(rows).to_csv(csv, index=False)
        result = train_keras_experiment(csv, experiment="keras_dlk1_smoke", epochs=2,
                                        batch_size=32, overwrite=True)
        print("DL-K1 SMOKE PASS — synthetic dataset ONLY")
        print("Real dataset scores must come from keras_dlk1.py, not this smoke test.")
        print("Artifact:", result["paths"]["model"])


if __name__ == "__main__":
    main()
