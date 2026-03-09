# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# scraper.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Navega WhatsApp Business Web y extrae las órdenes de la sección Orders."""

import re
import time
from datetime import date, datetime, timedelta
from typing import Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import SAMPLE_ORDERS

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
        self._status("🔍 Buscando Herramientas de empresa…")

        selectors = [
            '[data-testid="menu-bar-item-business-tools"]',
            '[data-testid="business-tools"]',
            '[aria-label="Tools"]',
            '[aria-label="Business tools"]',
            '[aria-label="Herramientas de empresa"]',
        ]
        if self._try_click(selectors):
            time.sleep(1.2)
            return True

        # Último recurso: último botón del nav lateral
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                'nav [role="button"], div[role="navigation"] [role="button"]')
            if btns:
                btns[-1].click()
                time.sleep(1.2)
                return True
        except Exception:
            pass

        self._status("⚠️  No se encontró el botón de Herramientas.")
        return False

    # ── Paso 2: abrir Orders ──────────────────────────────────────────────────
    def _open_orders(self) -> bool:
        self._status("📋 Abriendo sección de Pedidos…")

        if self._try_click([
            '[data-testid="menu-item-orders"]',
            '[aria-label="Orders"]',
            '[aria-label="Pedidos"]',
        ]):
            time.sleep(2)
            return True

        try:
            el = self.driver.find_element(
                By.XPATH,
                '//*[normalize-space(text())="Orders" or normalize-space(text())="Pedidos"]')
            el.click()
            time.sleep(2)
            return True
        except NoSuchElementException:
            pass

        self._status("⚠️  No se encontró la opción Pedidos.")
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

        time.sleep(1)
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

        # Pre-leer todos los hijos para no perder referencias tras navegar
        children = container.find_elements(By.XPATH, './*')

        for child in children:
            tag = child.tag_name.lower()

            # ── Encabezado de fecha ───────────────────────────────────────────────
            if tag == 'div':
                cur_date = self._parse_date_header(child.text.strip(), today)
                continue

            if tag != 'button':
                continue

            # ── Datos básicos desde la fila (sin navegar) ─────────────────────────
            order = self._parse_order_row(child, cur_date, len(orders))
            if not order:
                continue

            # ── Abrir detalle para obtener el ID real de WhatsApp ─────────────────
            order['id'] = self._fetch_order_id(child, len(orders))
            print(order)

            orders.append(order)
            self._status(f"📦 {len(orders)} orden(es) leída(s)…")

        self._status(f"✅ {len(orders)} pedido(s) importados · {datetime.now().strftime('%H:%M')}")
        return orders or SAMPLE_ORDERS


    def _fetch_order_id(self, btn, idx: int) -> str:
        """
        Hace clic en el botón de la orden, lee el ID del panel de detalle
        (ej: 'order #4UKRYVC6TNC') y vuelve a la lista.
        Devuelve el ID formateado o un fallback si algo falla.
        """
        fallback = f"ORD-{idx+1:03d}"

        try:
            btn.click()

            # Esperar a que cargue el panel de detalle:
            # busca el div que contiene el texto "order #XXXXX"
            detail_wait = WebDriverWait(self.driver, 10)
            id_el = detail_wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.xhslqc4'))
            )
            raw = id_el.text.strip()          # "order #4UKRYVC6TNC"
            print(raw)

            # Extraer solo el código alfanumérico tras el "#"
            match = re.search(r'#([A-Z0-9]+)', raw, re.I)
            order_id = match.group(1).upper() if match else raw

            # ── Volver a la lista ─────────────────────────────────────────────────
            #self._go_back()

            return order_id

        except Exception:
            print("la cague")
            return fallback


    def _go_back(self):
        """
        Hace clic en el botón Volver del panel de detalle y espera
        a que reaparezca la lista de órdenes.
        """
        back_selectors = [
            'button[aria-label="Back"]',
            'button[data-tab="2"]',             # data-tab que vimos en el HTML
            'button[aria-label="Volver"]',
        ]
        for sel in back_selectors:
            try:
                btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                btn.click()
                break
            except TimeoutException:
                continue

        # Esperar a que la lista vuelva a estar visible
        try:
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'button.x6s0dn4.x78zum5.xvt47uu')))
        except TimeoutException:
            pass

        time.sleep(0.8)   # pequeño margen para que el DOM se estabilice

    # ── Parseo de una fila de orden ───────────────────────────────────────────
    def _parse_order_row(self, btn, cur_date: date, idx: int) -> dict | None:
        try:
            order = {"id": f"ORD-{idx+1:03d}", "fecha": cur_date.isoformat()}

            # Cliente
            try:
                sp = btn.find_element(By.CSS_SELECTOR, 'span[dir="auto"][title]')
                order['cliente'] = sp.get_attribute('title') or sp.text.strip()
            except NoSuchElementException:
                order['cliente'] = btn.find_element(
                    By.CSS_SELECTOR, 'span[dir="auto"]').text.strip()

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

        except Exception:
            return {
                'id': f"ORD-ERR-{idx+1:03d}", 'cliente': 'Error al leer',
                'producto': '—', 'monto': 0.0,
                'fecha': cur_date.isoformat(), 'estado': 'Error',
            }

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _try_click(self, selectors: list[str], timeout: int = 10) -> bool:
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
        up = raw.upper()
        if up in ('TODAY', 'HOY'):
            return today
        if up in ('YESTERDAY', 'AYER'):
            return today - timedelta(days=1)
        for fmt in ('%d/%m/%Y', '%m/%d/%Y', '%d %b %Y', '%B %d, %Y'):
            try:
                return datetime.strptime(up, fmt).date()
            except ValueError:
                continue
        return today

