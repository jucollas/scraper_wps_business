# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# browser.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Detecta qué navegador está disponible y construye el driver de Selenium."""

import os
import sys
import time
import logging
import shutil

logger = logging.getLogger(__name__)

# ── Imports opcionales por navegador ─────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service  import Service as ChromeService
    from selenium.webdriver.chrome.options  import Options as ChromeOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.edge.service    import Service as EdgeService
    from selenium.webdriver.edge.options    import Options as EdgeOptions
    SELENIUM_OK = CHROME_OK = FIREFOX_OK = EDGE_OK = True
except ImportError:
    SELENIUM_OK = CHROME_OK = FIREFOX_OK = EDGE_OK = False

# webdriver_manager — solo como respaldo si Selenium Manager falla
try:
    from webdriver_manager.chrome    import ChromeDriverManager
    from webdriver_manager.firefox   import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    _WDM_OK = True
except ImportError:
    _WDM_OK = False

# Rutas comunes de ejecutables por navegador en Windows
_WIN_PATHS = {
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
}

_NON_WIN_BINARIES = {
    "edge": ["microsoft-edge", "msedge"],
    "chrome": ["google-chrome", "chrome", "chromium", "chromium-browser"],
    "firefox": ["firefox"],
}


def _browser_path(name: str) -> str | None:
    """Devuelve la ruta del ejecutable si el navegador está instalado."""
    if sys.platform == "win32":
        for path in _WIN_PATHS.get(name, []):
            if os.path.exists(path):
                return path
        return None

    for binary in _NON_WIN_BINARIES.get(name, []):
        path = shutil.which(binary)
        if path:
            return path
    return None


def _browser_installed(name: str) -> bool:
    """Verifica si el ejecutable del navegador existe en el sistema."""
    return _browser_path(name) is not None


def _detect_default_browser() -> str | None:
    """
    Devuelve 'chrome', 'firefox' o 'edge' según el navegador predeterminado
    del sistema operativo. Devuelve None si no se puede detectar.
    """
    platform = sys.platform  # variable local para evitar evaluación estática del linter

    if platform == "win32":
        # Método 1: registro de Windows (UserChoice para http)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\http\UserChoice")
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            winreg.CloseKey(key)
            prog_id = prog_id.lower()
            logger.info(f"ProgId del navegador predeterminado: {prog_id}")

            if "chrome" in prog_id:
                return "chrome"
            if "firefox" in prog_id:
                return "firefox"
            if "edge" in prog_id or "msedge" in prog_id:
                return "edge"
        except Exception as e:
            logger.warning(f"No se pudo leer el registro: {e}")

        # Método 2: verificar ejecutables instalados (Edge primero por ser el default de Windows)
        for name in ("edge", "chrome", "firefox"):
            if _browser_installed(name):
                logger.info(f"Navegador detectado por ejecutable: {name}")
                return name

    elif platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read",
                 "com.apple.LaunchServices/com.apple.launchservices.secure",
                 "LSHandlers"],
                capture_output=True, text=True)
            out = result.stdout.lower()
            if "chrome" in out:
                return "chrome"
            if "firefox" in out:
                return "firefox"
            if "edge" in out:
                return "edge"
        except Exception as e:
            logger.warning(f"macOS default browser detection failed: {e}")

    else:  # Linux
        try:
            import subprocess
            result = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True)
            out = result.stdout.lower()
            if "chrome" in out or "chromium" in out:
                return "chrome"
            if "firefox" in out:
                return "firefox"
            if "edge" in out or "msedge" in out:
                return "edge"
        except Exception as e:
            logger.warning(f"Linux default browser detection failed: {e}")

    return None


class BrowserManager:
    """
    Inicia Selenium sólo con navegadores realmente instalados.
    En Windows prioriza Chrome y Edge para evitar fallbacks inesperados a Firefox.
    """

    SESSION_BASE = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "wsp_session")
    )

    # Qué drivers de Selenium están disponibles
    _SDK_OK = property(lambda self: {
        "chrome":  CHROME_OK,
        "firefox": FIREFOX_OK,
        "edge":    EDGE_OK,
    })

    @staticmethod
    def available() -> bool:
        sdk_ok = {"chrome": CHROME_OK, "firefox": FIREFOX_OK, "edge": EDGE_OK}
        return SELENIUM_OK and any(
            sdk_ok[name] and _browser_installed(name) for name in sdk_ok
        )

    @staticmethod
    def missing_packages() -> list[str]:
        if not SELENIUM_OK:
            return ["selenium"]
        return []

    def build(self, headless: bool = False):
        """
        Devuelve (driver, nombre_browser).
        Usa sólo navegadores instalados. En Windows intenta Chrome/Edge antes de
        Firefox, salvo que Firefox sea el navegador predeterminado explícito.
        headless=True oculta la ventana del navegador.
        Lanza RuntimeError si ningún navegador funciona.
        """
        default = _detect_default_browser()
        sdk_ok  = {"chrome": CHROME_OK, "firefox": FIREFOX_OK, "edge": EDGE_OK}
        installed = {}
        for name, enabled in sdk_ok.items():
            if not enabled:
                continue
            browser_path = _browser_path(name)
            if browser_path:
                installed[name] = browser_path

        logger.info(f"Navegador predeterminado detectado: {default}")
        logger.info(f"Drivers disponibles: { {k: v for k, v in sdk_ok.items() if v} }")
        logger.info(f"Navegadores instalados: {installed}")

        # Siempre poner el navegador predeterminado primero
        order = []
        if default and default in installed:
            order.append(default)

        if sys.platform == "win32":
            fallback_order = ["edge", "chrome", "firefox"]
        else:
            fallback_order = ["chrome", "edge", "firefox"]

        for name in fallback_order:
            if name not in order and name in installed:
                order.append(name)

        if not order:
            raise RuntimeError(
                "No se encontró ningún navegador compatible instalado.\n"
                "Instala Chrome, Edge o Firefox y vuelve a intentarlo.\n\n"
                "Si faltan paquetes de Python, instala:\n"
                "  pip install selenium webdriver-manager")

        errors = []
        for name in order:
            # 1er intento: con el perfil guardado (conserva la sesión de WhatsApp)
            driver, label, error = self._try_build(name, headless)
            if driver:
                logger.info(f"Navegador iniciado: {label}")
                return driver, label
            if error:
                errors.append(f"{error} (perfil guardado)")
                logger.warning(f"Primer intento fallido para {name}: {error}. Reintentando con perfil nuevo…")

            # 2do intento: elimina el perfil corrompido y empieza limpio
            driver, label, error2 = self._try_build(name, headless, fresh=True)
            if driver:
                logger.warning(f"Navegador iniciado con perfil nuevo (sesión perdida): {label}")
                return driver, label
            if error2:
                errors.append(f"{error2} (perfil nuevo)")

        raise RuntimeError(
            "No se pudo iniciar ningún navegador.\n\n"
            "Errores:\n" + "\n".join(errors)
        )

    @staticmethod
    def _clean_locks(profile_path: str):
        """Elimina archivos de bloqueo que impiden arrancar el navegador."""
        for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket",
                     "lockfile", ".parentlock", "DevToolsActivePort",
                     "CrashpadMetrics-active.pma"):
            p = os.path.join(profile_path, lock)
            if os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"Lock eliminado: {p}")
                except OSError:
                    pass
        time.sleep(0.3)  # Pausa para que el SO libere los bloqueos

    def _try_build(self, name: str, headless: bool, fresh: bool = False):
        """Intenta construir el driver para el navegador dado. Devuelve (driver, label, error).
        Si fresh=True elimina el directorio de perfil antes de iniciar (pierde sesión guardada).
        """
        browser_path = _browser_path(name)
        if not browser_path:
            return None, None, f"{name.title()}: navegador no instalado"

        if name == "chrome":
            try:
                profile_path = f"{self.SESSION_BASE}_chrome"
                if fresh and os.path.exists(profile_path):
                    try:
                        shutil.rmtree(profile_path, ignore_errors=True)
                        logger.info(f"Perfil Chrome eliminado para inicio limpio: {profile_path}")
                    except Exception as ex:
                        logger.warning(f"No se pudo eliminar perfil Chrome: {ex}")
                os.makedirs(profile_path, exist_ok=True)
                self._clean_locks(profile_path)
                opts = ChromeOptions()
                opts.binary_location = browser_path
                opts.add_argument(f"--user-data-dir={profile_path}")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--no-first-run")
                opts.add_argument("--no-default-browser-check")
                opts.add_argument("--disable-extensions")
                opts.add_argument("--disable-background-networking")
                opts.add_argument("--disable-sync")
                opts.add_argument("--remote-debugging-port=0")
                if headless:
                    opts.add_argument("--headless=new")
                    opts.add_argument("--window-size=1280,900")
                # Selenium Manager (Selenium 4.6+) descarga el driver correcto automáticamente
                try:
                    return webdriver.Chrome(options=opts), "Chrome", None
                except Exception:
                    if _WDM_OK:
                        svc = ChromeService(ChromeDriverManager().install())
                        return webdriver.Chrome(service=svc, options=opts), "Chrome", None
                    raise
            except Exception as e:
                return None, None, f"Chrome: {e}"

        if name == "firefox":
            try:
                profile_path = f"{self.SESSION_BASE}_firefox"
                if fresh and os.path.exists(profile_path):
                    try:
                        shutil.rmtree(profile_path, ignore_errors=True)
                        logger.info(f"Perfil Firefox eliminado para inicio limpio: {profile_path}")
                    except Exception as ex:
                        logger.warning(f"No se pudo eliminar perfil Firefox: {ex}")
                os.makedirs(profile_path, exist_ok=True)
                self._clean_locks(profile_path)
                opts = FirefoxOptions()
                opts.binary_location = browser_path
                opts.add_argument("-profile")
                opts.add_argument(profile_path)
                if headless:
                    opts.add_argument("--headless")
                    opts.add_argument("--width=1280")
                    opts.add_argument("--height=900")
                try:
                    return webdriver.Firefox(options=opts), "Firefox", None
                except Exception:
                    if _WDM_OK:
                        svc = FirefoxService(GeckoDriverManager().install())
                        return webdriver.Firefox(service=svc, options=opts), "Firefox", None
                    raise
            except Exception as e:
                return None, None, f"Firefox: {e}"

        if name == "edge":
            try:
                profile_path = f"{self.SESSION_BASE}_edge"
                if fresh and os.path.exists(profile_path):
                    try:
                        shutil.rmtree(profile_path, ignore_errors=True)
                        logger.info(f"Perfil Edge eliminado para inicio limpio: {profile_path}")
                    except Exception as ex:
                        logger.warning(f"No se pudo eliminar perfil Edge: {ex}")
                os.makedirs(profile_path, exist_ok=True)
                self._clean_locks(profile_path)
                opts = EdgeOptions()
                opts.binary_location = browser_path
                opts.add_argument(f"--user-data-dir={profile_path}")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--no-first-run")
                opts.add_argument("--no-default-browser-check")
                opts.add_argument("--disable-extensions")
                opts.add_argument("--disable-background-networking")
                opts.add_argument("--disable-sync")
                opts.add_argument("--remote-debugging-port=0")
                if headless:
                    opts.add_argument("--headless=new")
                    opts.add_argument("--window-size=1280,900")
                try:
                    return webdriver.Edge(options=opts), "Edge", None
                except Exception:
                    if _WDM_OK:
                        svc = EdgeService(EdgeChromiumDriverManager().install())
                        return webdriver.Edge(service=svc, options=opts), "Edge", None
                    raise
            except Exception as e:
                return None, None, f"Edge: {e}"

        return None, None, None
