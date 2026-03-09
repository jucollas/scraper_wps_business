# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# browser.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Detecta qué navegador está disponible y construye el driver de Selenium."""

import os

# ── Imports opcionales por navegador ─────────────────────────────────────────
try:
    from selenium import webdriver

    try:
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from webdriver_manager.chrome import ChromeDriverManager
        CHROME_OK = True
    except ImportError:
        CHROME_OK = False

    try:
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from webdriver_manager.firefox import GeckoDriverManager
        FIREFOX_OK = True
    except ImportError:
        FIREFOX_OK = False

    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        EDGE_OK = True
    except ImportError:
        EDGE_OK = False

    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = CHROME_OK = FIREFOX_OK = EDGE_OK = False


class BrowserManager:
    """
    Responsabilidad única: detectar y crear el WebDriver disponible.
    Prueba Chrome → Firefox → Edge en ese orden.
    """

    SESSION_BASE = os.path.join(os.getcwd(), "wsp_session")

    @staticmethod
    def available() -> bool:
        return SELENIUM_OK and any([CHROME_OK, FIREFOX_OK, EDGE_OK])

    @staticmethod
    def missing_packages() -> list[str]:
        missing = []
        if not SELENIUM_OK:
            missing.append("selenium webdriver-manager")
        return missing

    def build(self):
        """
        Devuelve (driver, nombre_browser).
        Lanza RuntimeError si ningún navegador funciona.
        """
        errors = []

        if CHROME_OK:
            try:
                opts = ChromeOptions()
                opts.add_argument(f"--user-data-dir={self.SESSION_BASE}_chrome")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                svc = ChromeService(ChromeDriverManager().install())
                return webdriver.Chrome(service=svc, options=opts), "Chrome"
            except Exception as e:
                errors.append(f"Chrome: {e}")

        if FIREFOX_OK:
            try:
                profile_path = f"{self.SESSION_BASE}_firefox"
                os.makedirs(profile_path, exist_ok=True)
                opts = FirefoxOptions()
                opts.add_argument("-profile")
                opts.add_argument(profile_path)
                svc = FirefoxService(GeckoDriverManager().install())
                return webdriver.Firefox(service=svc, options=opts), "Firefox"
            except Exception as e:
                errors.append(f"Firefox: {e}")

        if EDGE_OK:
            try:
                opts = EdgeOptions()
                opts.add_argument(f"--user-data-dir={self.SESSION_BASE}_edge")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                svc = EdgeService(EdgeChromiumDriverManager().install())
                return webdriver.Edge(service=svc, options=opts), "Edge"
            except Exception as e:
                errors.append(f"Edge: {e}")

        raise RuntimeError(
            "No se encontró ningún navegador compatible.\n\n"
            "Instala Chrome, Firefox o Edge y:\n"
            "  pip install selenium webdriver-manager\n\n"
            "Errores:\n" + "\n".join(errors)
        )