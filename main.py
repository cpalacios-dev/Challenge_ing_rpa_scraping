# main.py
import os
from src.pipeline.runner import run_pipeline

if __name__ == "__main__":
    # Aseguramos que el script se ejecute correctamente independientemente de la ruta actual
    run_pipeline()