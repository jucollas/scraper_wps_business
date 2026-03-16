# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# main.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Punto de entrada. Ejecutar: python main.py"""

import logging
import importlib.util
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S")


def _load_app_class():
    app_path = Path(__file__).with_name("app.py")
    spec = importlib.util.spec_from_file_location("wbs_app_ui", app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {app_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.App


App = _load_app_class()

if __name__ == "__main__":
    App().mainloop()
