import os
import sys

if hasattr(sys, "_MEIPASS"):
    base = sys._MEIPASS

    # 1. XGBoost — add lib/ folder to PATH so xgboost.dll is found
    xgb_lib = os.path.join(base, "xgboost", "lib")
    if os.path.isdir(xgb_lib):
        os.environ["PATH"] = xgb_lib + os.pathsep + os.environ.get("PATH", "")

    # 2. SentenceTransformer — redirect HF cache to bundled model
    st_home = os.path.join(base, "sentence_transformers_models")
    if os.path.isdir(st_home):
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = st_home
        os.environ["HF_HOME"] = st_home
        os.environ["TRANSFORMERS_CACHE"] = st_home
        os.environ["HF_HUB_OFFLINE"] = "1"
