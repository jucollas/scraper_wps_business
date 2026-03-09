# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# app.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Ventana principal: construye la UI y orquesta browser, scraper y exporter."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import threading
import time

from config import (C_GREEN, C_DARK, C_LIGHT, C_BG, C_WHITE,
                    C_GRAY, C_ORANGE, SAMPLE_ORDERS)
from browser  import BrowserManager
from scraper  import OrderScraper
from exporter import Exporter, EXCEL_OK, PDF_OK


class App(tk.Tk):
    """
    Responsabilidad única: interfaz gráfica y coordinación entre módulos.
    No contiene lógica de scraping, exportación ni detección de navegador.
    """

    def __init__(self):
        super().__init__()
        self.title("WBS Order Manager")
        self.geometry("860x620")
        self.minsize(780, 560)
        self.configure(bg=C_BG)
        self.resizable(True, True)

        self.orders   = []
        self.driver   = None
        self.connected = False
        self._browser  = BrowserManager()
        self._exporter = Exporter()

        self._check_deps()
        self._build_ui()

    # ── Dependencias ──────────────────────────────────────────────────────────
    def _check_deps(self):
        missing = self._browser.missing_packages()
        if not EXCEL_OK: missing.append("openpyxl")
        if not PDF_OK:   missing.append("reportlab")
        if missing:
            messagebox.showwarning(
                "Dependencias faltantes",
                "Instálalos con:\n\npip install " + " ".join(missing))
        elif not self._browser.available():
            messagebox.showwarning(
                "Sin navegadores",
                "selenium está instalado pero no se encontró Chrome, Firefox ni Edge.")

    # ── Construcción de la UI ─────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_connection_panel()
        self._build_filter_bar()
        self._build_kpi_row()
        self._build_table()

        tk.Label(self, text="Sin datos cargados.", bg=C_BG, fg=C_GRAY,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 8))

        self._load_orders(SAMPLE_ORDERS)
        self._apply_filter()

    def _build_header(self):
        hdr = tk.Frame(self, bg=C_DARK, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⬡",           bg=C_DARK, fg=C_GREEN,
                 font=("Segoe UI", 22)).pack(side="left", padx=(16, 6), pady=8)
        tk.Label(hdr, text="WBS Order Manager", bg=C_DARK, fg=C_WHITE,
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        self.lbl_status = tk.Label(hdr, text="● Desconectado",
                                   bg=C_DARK, fg="#F87171", font=("Segoe UI", 10))
        self.lbl_status.pack(side="left", padx=20)

        self.lbl_update = tk.Label(hdr, text="", bg=C_DARK, fg="#9CA3AF",
                                   font=("Segoe UI", 9))
        self.lbl_update.pack(side="right", padx=16)

    def _build_connection_panel(self):
        card = self._card(self)
        inner = tk.Frame(card, bg=C_WHITE)
        inner.pack(padx=20, pady=14, fill="x")

        tk.Label(inner, text="Vinculación de cuenta", bg=C_WHITE, fg=C_DARK,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(inner,
                 text="WhatsApp Business → Menú → Dispositivos vinculados → Escanea el QR",
                 bg=C_WHITE, fg=C_GRAY, font=("Segoe UI", 9)).pack(side="left", padx=14)

        self.btn_disconnect = tk.Button(
            inner, text="Desconectar", bg="#F3F4F6", fg=C_GRAY,
            font=("Segoe UI", 9), relief="flat", padx=10, pady=6,
            cursor="hand2", command=self._disconnect)
        self.btn_disconnect.pack(side="right", padx=6)
        self.btn_disconnect.pack_forget()

        self.btn_connect = tk.Button(
            inner, text="📱  Conectar con WhatsApp Web",
            bg=C_GREEN, fg=C_WHITE, font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            command=self._connect)
        self.btn_connect.pack(side="right")

    def _build_filter_bar(self):
        card  = self._card(self, top_pad=10)
        row   = tk.Frame(card, bg=C_WHITE)
        row.pack(padx=20, pady=12, fill="x")

        tk.Label(row, text="🗓  Desde:", bg=C_WHITE, fg=C_DARK,
                 font=("Segoe UI", 10)).pack(side="left")
        self.entry_from = ttk.Entry(row, width=13, font=("Segoe UI", 10))
        self.entry_from.insert(0, "2025-02-01")
        self.entry_from.pack(side="left", padx=(6, 18))

        tk.Label(row, text="Hasta:", bg=C_WHITE, fg=C_DARK,
                 font=("Segoe UI", 10)).pack(side="left")
        self.entry_to = ttk.Entry(row, width=13, font=("Segoe UI", 10))
        self.entry_to.insert(0, date.today().isoformat())
        self.entry_to.pack(side="left", padx=6)

        tk.Button(row, text="🔍  Filtrar", bg=C_DARK, fg=C_WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=5,
                  cursor="hand2", command=self._apply_filter).pack(side="left", padx=14)

        tk.Button(row, text="📊  Exportar Excel", bg="#10B981", fg=C_WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._export_excel).pack(side="right", padx=(6, 0))
        tk.Button(row, text="📄  Exportar PDF", bg="#6366F1", fg=C_WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=12, pady=5,
                  cursor="hand2", command=self._export_pdf).pack(side="right", padx=6)

    def _build_kpi_row(self):
        frame = tk.Frame(self, bg=C_BG)
        frame.pack(fill="x", padx=20, pady=(10, 0))

        self.kpi_vars = {
            "total":      tk.StringVar(value="$0.00"),
            "count":      tk.StringVar(value="0"),
            "completado": tk.StringVar(value="0"),
            "pendiente":  tk.StringVar(value="0"),
        }
        for label, key, color in [
            ("💰 Total facturado", "total",      C_GREEN),
            ("📦 Órdenes",        "count",      C_DARK),
            ("✅ Completadas",    "completado", "#10B981"),
            ("⏳ Pendientes",     "pendiente",  C_ORANGE),
        ]:
            c = tk.Frame(frame, bg=C_WHITE, width=160,
                         highlightthickness=1, highlightbackground="#E5E7EB")
            c.pack(side="left", expand=True, fill="x", padx=(0, 10))
            tk.Label(c, text=label,  bg=C_WHITE, fg=C_GRAY,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(c, textvariable=self.kpi_vars[key], bg=C_WHITE, fg=color,
                     font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=14, pady=(0, 10))

    def _build_table(self):
        frame = tk.Frame(self, bg=C_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=(10, 16))

        cols = ("ID", "Cliente", "Producto", "Fecha", "Monto", "Estado")
        sty  = ttk.Style()
        sty.theme_use("clam")
        sty.configure("T.Treeview", background=C_WHITE, fieldbackground=C_WHITE,
                       rowheight=30, font=("Segoe UI", 10))
        sty.configure("T.Treeview.Heading", background=C_DARK, foreground=C_WHITE,
                       font=("Segoe UI", 10, "bold"), relief="flat")
        sty.map("T.Treeview",
                background=[("selected", C_LIGHT)],
                foreground=[("selected", C_DARK)])

        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  style="T.Treeview", selectmode="extended")
        for col, w in zip(cols, [80, 170, 160, 100, 90, 100]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        self.tree.tag_configure("completado", foreground="#065F46")
        self.tree.tag_configure("pendiente",  foreground="#92400E")
        self.tree.tag_configure("cancelado",  foreground="#991B1B")
        self.tree.tag_configure("error",      foreground="#6B7280")

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.lbl_count = tk.Label(self, text="Sin datos cargados.",
                                  bg=C_BG, fg=C_GRAY, font=("Segoe UI", 9))
        self.lbl_count.pack(anchor="w", padx=22, pady=(0, 8))

    # ── Conexión ──────────────────────────────────────────────────────────────
    def _connect(self):
        self.btn_connect.config(state="disabled", text="Abriendo navegador…")
        threading.Thread(target=self._open_whatsapp, daemon=True).start()

    def _open_whatsapp(self):
        try:
            self.driver, browser = self._browser.build()
            self.after(0, lambda: self.lbl_update.config(text=f"Navegador: {browser}"))
            self.driver.get("https://web.whatsapp.com")

            self.after(0, lambda: self.lbl_status.config(
                text="● Esperando escaneo QR…", fg=C_ORANGE))
            self.after(0, lambda: self.btn_connect.config(text="📱  Esperando QR…"))

            for _ in range(60):
                page = self.driver.page_source
                if 'data-testid="chat-list"' in page or "_3q4NP" in page:
                    break
                time.sleep(1)

            scraper = OrderScraper(
                self.driver,
                on_status=lambda msg: self.after(0, lambda m=msg: self.lbl_update.config(text=m))
            )
            self._load_orders(scraper.fetch())
            self.connected = True
            self.after(0, self._on_connected)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error de conexión", str(e)))
            self.after(0, self._reset_connect_btn)

    def _on_connected(self):
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.lbl_status.config(text="● Conectado", fg=C_GREEN)
        self.lbl_update.config(text=f"Última actualización: {ts}")
        self.btn_connect.pack_forget()
        self.btn_disconnect.pack(side="right")
        self._apply_filter()

    def _disconnect(self):
        if self.driver:
            try: self.driver.quit()
            except: pass
            self.driver = None
        self.connected = False
        self.lbl_status.config(text="● Desconectado", fg="#F87171")
        self.lbl_update.config(text="")
        self.btn_disconnect.pack_forget()
        self.btn_connect.pack(side="right")
        self._reset_connect_btn()

    def _reset_connect_btn(self):
        self.btn_connect.config(state="normal", text="📱  Conectar con WhatsApp Web")

    # ── Datos y tabla ─────────────────────────────────────────────────────────
    def _load_orders(self, orders):
        self.orders = orders

    def _apply_filter(self):
        d_from = self.entry_from.get().strip()
        d_to   = self.entry_to.get().strip()
        try:
            datetime.strptime(d_from, "%Y-%m-%d")
            datetime.strptime(d_to,   "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha inválida", "Usa el formato YYYY-MM-DD")
            return

        filtered = [o for o in self.orders if d_from <= o["fecha"] <= d_to]
        self._refresh_table(filtered)
        self._refresh_kpis(filtered)
        self.lbl_count.config(
            text=f"{len(filtered)} orden(es)  ·  {d_from} → {d_to}")

    def _refresh_table(self, orders):
        self.tree.delete(*self.tree.get_children())
        for o in sorted(orders, key=lambda x: x["fecha"], reverse=True):
            self.tree.insert("", "end",
                             values=(o["id"], o["cliente"], o["producto"],
                                     o["fecha"], f"${o['monto']:.2f}", o["estado"]),
                             tags=(o["estado"].lower(),))

    def _refresh_kpis(self, orders):
        total = sum(o["monto"] for o in orders)
        self.kpi_vars["total"].set(f"${total:,.2f}")
        self.kpi_vars["count"].set(str(len(orders)))
        self.kpi_vars["completado"].set(str(sum(1 for o in orders if o["estado"] == "Completado")))
        self.kpi_vars["pendiente"].set(str(sum(1 for o in orders if o["estado"] == "Pendiente")))

    def _get_filtered_orders(self):
        d_from = self.entry_from.get().strip()
        d_to   = self.entry_to.get().strip()
        return [o for o in self.orders if d_from <= o["fecha"] <= d_to]

    # ── Exportación (delega en Exporter) ─────────────────────────────────────
    def _export_excel(self):
        ok, msg = self._exporter.to_excel(self._get_filtered_orders())
        (messagebox.showinfo if ok else messagebox.showerror)("Excel", msg)

    def _export_pdf(self):
        ok, msg = self._exporter.to_pdf(
            self._get_filtered_orders(),
            self.entry_from.get(), self.entry_to.get())
        (messagebox.showinfo if ok else messagebox.showerror)("PDF", msg)

    # ── Helper UI ─────────────────────────────────────────────────────────────
    @staticmethod
    def _card(parent, top_pad=14):
        wrap = tk.Frame(parent, bg="#F0F4F8")
        wrap.pack(fill="x", padx=20, pady=(top_pad, 0))
        card = tk.Frame(wrap, bg=C_WHITE,
                        highlightthickness=1, highlightbackground="#E5E7EB")
        card.pack(fill="x")
        return card

