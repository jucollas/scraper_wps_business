# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# scraper.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Navega WhatsApp Business Web y extrae las órdenes de la sección Orders."""

import re
import time
import logging
from datetime import date, datetime, timedelta
from typing import Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from config import SAMPLE_ORDERS

logger = logging.getLogger(__name__)

ESTADO_MAP = {
    'payment requested': 'Pendiente',
    'pago solicitado':   'Pendiente',
    'pending':           'Pendiente',
    'pendiente':         'Pendiente',
    'completed':         'Completado',
    'completado':        'Completado',
    'delivered':         'Completado',
    'entregado':         'Completado',
    'cancelled':         'Cancelado',
    'cancelado':         'Cancelado',
}

# Nombres de meses en español e inglés para parseo de fechas
MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}


class OrderScraper:
    """
    Responsabilidad única: extraer órdenes de WhatsApp Business Web.
    Recibe un driver activo y un callback de estado para actualizar la UI.
    """

    def __init__(self, driver, on_status: Callable[[str], None] = None):
        self.driver = driver
        self._status = on_status or (lambda msg: None)
        self._wait   = WebDriverWait(driver, 15)

    # ── Punto de entrada público ──────────────────────────────────────────────
    def fetch(self) -> list[dict]:
        if not self._open_business_tools():
            return SAMPLE_ORDERS
        if not self._open_orders():
            return SAMPLE_ORDERS
        return self._read_order_list()

    # ── Paso 1: abrir Business Tools ─────────────────────────────────────────
    def _open_business_tools(self) -> bool:
        self._status("Buscando Herramientas de empresa…")

        selectors = [
            '[data-testid="menu-bar-item-business-tools"]',
            '[data-testid="business-tools"]',
            '[aria-label="Tools"]',
            '[aria-label="Business tools"]',
            '[aria-label="Herramientas de empresa"]',
        ]
        if self._try_click(selectors):
            time.sleep(1)
            return True

        # Último recurso: último botón del nav lateral
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                'nav [role="button"], div[role="navigation"] [role="button"]')
            if btns:
                btns[-1].click()
                time.sleep(1)
                return True
        except Exception:
            pass

        self._status("⚠️  No se encontró el menú de Herramientas. Recuerda que necesitas tener WhatsApp Business para tener activados los pedidos.")
        return False

    # ── Paso 2: abrir Orders ──────────────────────────────────────────────────
    def _open_orders(self) -> bool:
        self._status("Abriendo sección de Pedidos…")

        if self._try_click([
            '[data-testid="menu-item-orders"]',
            '[aria-label="Orders"]',
            '[aria-label="Pedidos"]',
        ]):
            time.sleep(1.5)
            return True

        try:
            el = self.driver.find_element(
                By.XPATH,
                '//*[normalize-space(text())="Orders" or normalize-space(text())="Pedidos"]')
            el.click()
            time.sleep(1.5)
            return True
        except NoSuchElementException:
            pass

        self._status("⚠️  No se encontró la sección de Pedidos. Recuerda que necesitas tener WhatsApp Business para tener activados los pedidos.")
        return False

    # ── Paso 3: leer la lista de órdenes ─────────────────────────────────────
    def _read_order_list(self) -> list[dict]:
        self._status("⏳ Esperando panel de pedidos…")
        try:
            self._wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'button.x6s0dn4.x78zum5.xvt47uu')))
        except TimeoutException:
            self._status("⚠️  Panel de pedidos no cargó.")
            return SAMPLE_ORDERS

        time.sleep(0.8)
        self._status("📦 Leyendo lista de pedidos…")

        orders   = []
        today    = date.today()
        cur_date = today

        try:
            container = self.driver.find_element(
                By.CSS_SELECTOR,
                'div.x1280gxy.x94v8gs.xw2csxc.x1odjw0f.x1n2onr6')
        except NoSuchElementException:
            self._status("⚠️  Contenedor de órdenes no encontrado.")
            return SAMPLE_ORDERS

        # Pre-leer los hijos para construir lista de trabajo
        children = container.find_elements(By.XPATH, './*')
        # Guardamos XPATH de cada hijo para re-localizarlos tras navegar
        child_xpaths = []
        for i, child in enumerate(children):
            tag = child.tag_name.lower()
            child_xpaths.append((tag, i + 1))  # (tag, posición 1-based)

        # Primera pasada: extraer datos básicos sin navegar
        rows_data = []
        for child, (tag, pos) in zip(children, child_xpaths):
            if tag == 'div':
                cur_date = self._parse_date_header(child.text.strip(), today)
                rows_data.append(('date', cur_date))
            elif tag == 'button':
                order = self._parse_order_row(child, cur_date, len([r for r in rows_data if r[0] == 'order']))
                if order:
                    rows_data.append(('order', order))

        # Segunda pasada: navegar a cada orden para obtener el ID real
        order_count = 0
        for i, (rtype, data) in enumerate(rows_data):
            if rtype != 'order':
                continue

            order = data
            # Re-localizar el botón en el DOM actual
            btn = self._find_order_button(order_count, container)
            if btn is not None:
                order['id'] = self._fetch_order_id(btn, order_count)
                # Después de volver, re-localizar el container
                try:
                    container = self.driver.find_element(
                        By.CSS_SELECTOR,
                        'div.x1280gxy.x94v8gs.xw2csxc.x1odjw0f.x1n2onr6')
                except NoSuchElementException:
                    pass

            orders.append(order)
            order_count += 1
            self._status(f"📦 {len(orders)} orden(es) leída(s)…")

        self._status(f"✅ {len(orders)} pedido(s) importados · {datetime.now().strftime('%H:%M')}")
        return orders or SAMPLE_ORDERS

    def _find_order_button(self, idx: int, container):
        """Re-localiza el idx-ésimo botón dentro del container."""
        try:
            btns = container.find_elements(By.XPATH, './/button')
            if idx < len(btns):
                return btns[idx]
        except StaleElementReferenceException:
            pass
        return None

    def _fetch_order_id(self, btn, idx: int) -> str:
        """
        Hace clic en el botón de la orden, lee el ID del panel de detalle
        y vuelve a la lista. Devuelve el ID formateado o un fallback.
        """
        fallback = f"ORD-{idx+1:03d}"

        try:
            btn.click()
            time.sleep(0.5)

            # Esperar panel de detalle con múltiples selectores posibles
            detail_wait = WebDriverWait(self.driver, 8)
            id_el = None
            for sel in ['div.xhslqc4', '[data-testid="order-id"]', 'div[class*="order"] span']:
                try:
                    id_el = detail_wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                    break
                except TimeoutException:
                    continue

            order_id = fallback
            if id_el:
                raw = id_el.text.strip()
                match = re.search(r'#([A-Z0-9]+)', raw, re.I)
                order_id = match.group(1).upper() if match else (raw or fallback)

            self._go_back()
            return order_id

        except Exception as e:
            logger.warning(f"No se pudo obtener ID de orden {idx}: {e}")
            try:
                self._go_back()
            except Exception:
                pass
            return fallback

    def _go_back(self):
        """
        Hace clic en el botón Volver del panel de detalle y espera
        a que reaparezca la lista de órdenes.
        """
        back_selectors = [
            'button[aria-label="Back"]',
            'button[aria-label="Volver"]',
            'button[aria-label="Atrás"]',
            'button[data-tab="2"]',
        ]
        for sel in back_selectors:
            try:
                btn = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                btn.click()
                break
            except TimeoutException:
                continue

        # Intentar también con JS si los selectores fallan (botón de navegador)
        try:
            WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'button.x6s0dn4.x78zum5.xvt47uu')))
        except TimeoutException:
            # Si no aparece la lista, intentar con el botón atrás del navegador
            try:
                self.driver.execute_script("window.history.back()")
                time.sleep(1)
            except Exception:
                pass

        time.sleep(0.6)

    # ── Parseo de una fila de orden ───────────────────────────────────────────
    def _parse_order_row(self, btn, cur_date: date, idx: int) -> dict | None:
        try:
            order = {"id": f"ORD-{idx+1:03d}", "fecha": cur_date.isoformat()}

            # Cliente
            try:
                sp = btn.find_element(By.CSS_SELECTOR, 'span[dir="auto"][title]')
                order['cliente'] = sp.get_attribute('title') or sp.text.strip()
            except NoSuchElementException:
                try:
                    order['cliente'] = btn.find_element(
                        By.CSS_SELECTOR, 'span[dir="auto"]').text.strip()
                except NoSuchElementException:
                    order['cliente'] = 'Desconocido'

            # Monto
            monto_raw = next(
                (sp.text.strip()
                 for sp in btn.find_elements(By.TAG_NAME, 'span')
                 if re.search(r'(COP|USD|EUR|\$)', sp.text, re.I)),
                '')
            nums = re.sub(r'[^\d.]', '', monto_raw.replace(',', ''))
            order['monto'] = float(nums) if nums else 0.0

            # Producto
            producto = next(
                (sp.get_attribute('title').strip()
                 for sp in btn.find_elements(By.CSS_SELECTOR, 'span[title]')
                 if sp.get_attribute('title')
                 and not re.fullmatch(r'[\d\s\+\-]+', sp.get_attribute('title').strip())),
                'Sin descripción')
            order['producto'] = producto

            # Estado
            estado_raw = next(
                (sp.text.strip()
                 for sp in reversed(btn.find_elements(By.TAG_NAME, 'span'))
                 if sp.text.strip()
                 and not (sp.get_attribute('title') or '')
                 and not re.search(r'(COP|USD|\$)', sp.text, re.I)),
                '')
            order['estado'] = ESTADO_MAP.get(estado_raw.lower(), estado_raw or 'Desconocido')

            return order

        except Exception as e:
            logger.warning(f"Error parseando fila de orden {idx}: {e}")
            return {
                'id': f"ORD-ERR-{idx+1:03d}", 'cliente': 'Error al leer',
                'producto': '—', 'monto': 0.0,
                'fecha': cur_date.isoformat(), 'estado': 'Error',
            }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _try_click(self, selectors: list[str], timeout: int = 8) -> bool:
        w = WebDriverWait(self.driver, timeout)
        for sel in selectors:
            try:
                w.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel))).click()
                return True
            except TimeoutException:
                continue
        return False

    @staticmethod
    def _parse_date_header(raw: str, today: date) -> date:
        if not raw:
            return today

        up = raw.strip().upper()

        # Palabras clave
        if up in ('TODAY', 'HOY'):
            return today
        if up in ('YESTERDAY', 'AYER'):
            return today - timedelta(days=1)

        # Formatos numéricos estándar
        for fmt in ('%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y-%m-%d',
                    '%d/%m/%y', '%d %b %Y', '%B %d, %Y',
                    '%d de %B de %Y', '%d %B %Y'):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue

        # Parseo manual con meses en español: "15 de marzo de 2025" o "15 marzo 2025"
        match = re.search(
            r'(\d{1,2})\s+(?:de\s+)?([a-záéíóúüñ]+)(?:\s+(?:de\s+)?(\d{4}))?',
            raw.strip(), re.I)
        if match:
            day  = int(match.group(1))
            mes  = match.group(2).lower()
            year = int(match.group(3)) if match.group(3) else today.year
            if mes in MESES_ES:
                try:
                    return date(year, MESES_ES[mes], day)
                except ValueError:
                    pass

        # "Mar 15" o "March 15" sin año → año actual
        match2 = re.search(r'([a-záéíóúüñ]+)\s+(\d{1,2})', raw.strip(), re.I)
        if match2:
            mes = match2.group(1).lower()
            day = int(match2.group(2))
            if mes in MESES_ES:
                try:
                    return date(today.year, MESES_ES[mes], day)
                except ValueError:
                    pass

        return today
