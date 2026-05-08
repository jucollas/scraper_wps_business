# app.py  —  SaaS-style UI  (customtkinter + matplotlib)
"""Ventana principal: Panel + Analítica con graficos matplotlib."""

import io
import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
from collections import defaultdict
import threading
import time
import calendar

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.ticker as mticker
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

try:
    from tkcalendar import DateEntry
    CAL_OK = True
except ImportError:
    CAL_OK = False

from config import SAMPLE_ORDERS, DEBUG_VISUAL
from browser  import BrowserManager
from scraper  import OrderScraper
from exporter import Exporter, EXCEL_OK, PDF_OK
from database import Database

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

SIDEBAR_BG      = "#0F172A"
SIDEBAR_SECTION = "#1E293B"
SIDEBAR_HOVER   = "#334155"
SIDEBAR_ACTIVE  = "#4F46E5"
CONTENT_BG      = "#F1F5F9"
CARD_BG         = "#FFFFFF"
BORDER          = "#E2E8F0"
PRIMARY         = "#4F46E5"
PRIMARY_HOVER   = "#4338CA"
SUCCESS         = "#10B981"
SUCCESS_LIGHT   = "#D1FAE5"
WARNING         = "#F59E0B"
WARNING_LIGHT   = "#FEF3C7"
DANGER          = "#EF4444"
WA_GREEN        = "#25D366"
WA_DARK         = "#075E54"
TEXT_TITLE      = "#0F172A"
TEXT_PRIMARY    = "#1E293B"
TEXT_SECONDARY  = "#64748B"
TEXT_MUTED      = "#94A3B8"

CHART_COLORS = ["#4F46E5","#10B981","#F59E0B","#EF4444","#8B5CF6",
                "#06B6D4","#EC4899","#84CC16"]

# Fuente para emoji — en Windows usa "Segoe UI Emoji" para renderizar correctamente
EF = "Segoe UI Emoji" if sys.platform == "win32" else "Apple Color Emoji"

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
MESES_CORTOS = ["Ene","Feb","Mar","Abr","May","Jun",
                "Jul","Ago","Sep","Oct","Nov","Dic"]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WBS Order Manager")
        self.geometry("1260x820")
        self.minsize(1000, 660)
        self.orders        = []
        self.driver        = None
        self.connected     = False
        self.is_auto_sync  = False
        self._sort_col     = None
        self._sort_rev     = False
        self._current_page = "panel"
        self._driver_lock  = threading.RLock()
        self._browser  = BrowserManager()
        self._exporter = Exporter()
        self._db       = Database()
        self._check_deps()
        self._build_ui()
        saved = self._db.get_all()
        if saved:
            self._load_orders(saved)
            self._apply_filter()
            ts = datetime.now().strftime("%d/%m/%Y %H:%M")
            self._set_status_text(f"Datos locales · {ts}")

    def _check_deps(self):
        missing = self._browser.missing_packages()
        if not EXCEL_OK:      missing.append("openpyxl")
        if not PDF_OK:        missing.append("reportlab")
        if not MATPLOTLIB_OK: missing.append("matplotlib")
        if missing:
            messagebox.showwarning("Dependencias faltantes",
                "Instalalos con:\n\npip install " + " ".join(missing))
        elif not self._browser.available():
            messagebox.showwarning("Sin navegadores",
                "selenium instalado pero no se encontro Chrome, Firefox ni Edge.")

    # ──────────────────────────────────────────────────────────────────────────
    # LAYOUT RAIZ
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()

    # ──────────────────────────────────────────────────────────────────────────
    # SIDEBAR
    # ──────────────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=252, corner_radius=0, fg_color=SIDEBAR_BG)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(3, weight=1)

        logo_wrap = ctk.CTkFrame(sb, fg_color="transparent")
        logo_wrap.grid(row=0, column=0, padx=20, pady=(28, 20), sticky="ew")
        ctk.CTkLabel(logo_wrap, text="⬡", font=ctk.CTkFont(family=EF, size=30, weight="bold"),
                     text_color=WA_GREEN).pack(side="left", padx=(0, 12))
        nc = ctk.CTkFrame(logo_wrap, fg_color="transparent")
        nc.pack(side="left")
        ctk.CTkLabel(nc, text="WBS Manager",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#F8FAFC").pack(anchor="w")
        ctk.CTkLabel(nc, text="WhatsApp Business",
                     font=ctk.CTkFont(size=10), text_color=TEXT_MUTED).pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=SIDEBAR_SECTION).grid(
            row=1, column=0, padx=16, pady=0, sticky="ew")

        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.grid(row=2, column=0, padx=12, pady=(20, 0), sticky="ew")
        ctk.CTkLabel(nav, text="MENU PRINCIPAL",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(0, 8))

        self._nav_btn_panel = ctk.CTkButton(
            nav, text="  📊   Panel", anchor="w",
            fg_color=SIDEBAR_ACTIVE, hover_color=SIDEBAR_HOVER,
            text_color="#FFFFFF", font=ctk.CTkFont(family=EF, size=13, weight="bold"),
            height=40, corner_radius=8,
            command=lambda: self._show_page("panel"))
        self._nav_btn_panel.pack(fill="x", padx=4, pady=2)

        self._nav_btn_analytics = ctk.CTkButton(
            nav, text="  📈   Analítica", anchor="w",
            fg_color="transparent", hover_color=SIDEBAR_HOVER,
            text_color=TEXT_MUTED, font=ctk.CTkFont(family=EF, size=13),
            height=40, corner_radius=8,
            command=lambda: self._show_page("analytics"))
        self._nav_btn_analytics.pack(fill="x", padx=4, pady=2)

        self._nav_btn_reports = ctk.CTkButton(
            nav, text="  📄   Reportes", anchor="w",
            fg_color="transparent", hover_color=SIDEBAR_HOVER,
            text_color=TEXT_MUTED, font=ctk.CTkFont(family=EF, size=13),
            height=40, corner_radius=8,
            command=lambda: self._show_page("reports"))
        self._nav_btn_reports.pack(fill="x", padx=4, pady=2)

        ctk.CTkFrame(sb, fg_color="transparent").grid(row=3, column=0, sticky="nsew")
        ctk.CTkFrame(sb, height=1, fg_color=SIDEBAR_SECTION).grid(
            row=4, column=0, padx=16, pady=0, sticky="ew")

        conn = ctk.CTkFrame(sb, fg_color="transparent")
        conn.grid(row=5, column=0, padx=16, pady=(16, 0), sticky="ew")
        ctk.CTkLabel(conn, text="CONEXION",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 10))

        sc = ctk.CTkFrame(conn, fg_color=SIDEBAR_SECTION, corner_radius=10)
        sc.pack(fill="x", pady=(0, 12))
        si = ctk.CTkFrame(sc, fg_color="transparent")
        si.pack(padx=14, pady=12, fill="x")
        self._lbl_dot = ctk.CTkLabel(si, text="●",
                                     font=ctk.CTkFont(size=12), text_color=DANGER)
        self._lbl_dot.pack(side="left")
        tc = ctk.CTkFrame(si, fg_color="transparent")
        tc.pack(side="left", padx=(10, 0))
        self._lbl_conn_title = ctk.CTkLabel(tc, text="Desconectado",
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             text_color="#F8FAFC")
        self._lbl_conn_title.pack(anchor="w")
        self.lbl_update = ctk.CTkLabel(tc, text="Sin sincronizar",
                                        font=ctk.CTkFont(size=9), text_color=TEXT_MUTED,
                                        wraplength=150, justify="left")
        self.lbl_update.pack(anchor="w")

        self.btn_connect = ctk.CTkButton(
            conn, text="📱  Conectar WhatsApp",
            fg_color=WA_GREEN, hover_color=WA_DARK, text_color="white",
            font=ctk.CTkFont(family=EF, size=12, weight="bold"), height=40, corner_radius=8,
            command=self._connect)
        self.btn_connect.pack(fill="x", pady=(0, 6))

        self.btn_sync = ctk.CTkButton(
            conn, text="🔄  Sincronización Manual",
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="white",
            font=ctk.CTkFont(family=EF, size=12), height=38, corner_radius=8,
            command=self._sync)
        self.btn_sync.pack(fill="x", pady=(0, 4))
        self.btn_sync.pack_forget()

        self.btn_sync_auto = ctk.CTkButton(
            conn, text="🤖  Sincronización Automática",
            fg_color="#8B5CF6", hover_color="#7C3AED", text_color="white",
            font=ctk.CTkFont(family=EF, size=12), height=38, corner_radius=8,
            command=self._toggle_auto_sync)
        self.btn_sync_auto.pack(fill="x", pady=(0, 4))
        self.btn_sync_auto.pack_forget()

        self.btn_disconnect = ctk.CTkButton(
            conn, text="Desconectar",
            fg_color="transparent", hover_color=SIDEBAR_HOVER, text_color=TEXT_MUTED,
            border_width=1, border_color=SIDEBAR_SECTION,
            font=ctk.CTkFont(size=11), height=32, corner_radius=8,
            command=self._disconnect)
        self.btn_disconnect.pack(fill="x")
        self.btn_disconnect.pack_forget()

        ctk.CTkLabel(sb, text="v1.0.0 · WBS Order Manager",
                     font=ctk.CTkFont(size=9), text_color=TEXT_MUTED).grid(
            row=7, column=0, padx=16, pady=(8, 16))

    # ──────────────────────────────────────────────────────────────────────────
    # CAMBIO DE PAGINA
    # ──────────────────────────────────────────────────────────────────────────
    def _show_page(self, page: str):
        self._current_page = page
        # Ocultar todas las páginas
        self._panel_page.grid_remove()
        self._analytics_page.grid_remove()
        self._reports_page.grid_remove()
        # Resetear botones
        self._nav_btn_panel.configure(fg_color="transparent", text_color=TEXT_MUTED,
                                      font=ctk.CTkFont(family=EF, size=13))
        self._nav_btn_analytics.configure(fg_color="transparent", text_color=TEXT_MUTED,
                                          font=ctk.CTkFont(family=EF, size=13))
        self._nav_btn_reports.configure(fg_color="transparent", text_color=TEXT_MUTED,
                                        font=ctk.CTkFont(family=EF, size=13))
        if page == "panel":
            self._panel_page.grid(row=0, column=0, sticky="nsew")
            self._lbl_topbar_title.configure(text="Panel")
            self._lbl_topbar_subtitle.configure(
                text="Gestión de pedidos · WhatsApp Business")
            self._nav_btn_panel.configure(fg_color=SIDEBAR_ACTIVE, text_color="#FFFFFF",
                                          font=ctk.CTkFont(family=EF, size=13, weight="bold"))
        elif page == "analytics":
            self._analytics_page.grid(row=0, column=0, sticky="nsew")
            self._lbl_topbar_title.configure(text="Analítica")
            self._lbl_topbar_subtitle.configure(
                text="Métricas de ventas · WhatsApp Business")
            self._nav_btn_analytics.configure(fg_color=SIDEBAR_ACTIVE, text_color="#FFFFFF",
                                              font=ctk.CTkFont(family=EF, size=13, weight="bold"))
            self._refresh_analytics()
        else:  # reports
            self._reports_page.grid(row=0, column=0, sticky="nsew")
            self._lbl_topbar_title.configure(text="Reportes")
            self._lbl_topbar_subtitle.configure(
                text="Historial de reportes generados")
            self._nav_btn_reports.configure(fg_color=SIDEBAR_ACTIVE, text_color="#FFFFFF",
                                            font=ctk.CTkFont(family=EF, size=13, weight="bold"))
            self._refresh_reports()

    # ──────────────────────────────────────────────────────────────────────────
    # CONTENIDO PRINCIPAL
    # ──────────────────────────────────────────────────────────────────────────
    def _build_content(self):
        content = ctk.CTkFrame(self, fg_color=CONTENT_BG, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        self._build_topbar(content)

        pc = tk.Frame(content, bg=CONTENT_BG)
        pc.grid(row=1, column=0, sticky="nsew")
        pc.grid_columnconfigure(0, weight=1)
        pc.grid_rowconfigure(0, weight=1)

        self._build_panel_page(pc)
        self._build_analytics_page(pc)
        self._build_reports_page(pc)
        self._build_statusbar(content)
        self._show_page("panel")

    def _build_topbar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=28, pady=16)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left")
        self._lbl_topbar_title = ctk.CTkLabel(
            left, text="Panel",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_TITLE)
        self._lbl_topbar_title.pack(anchor="w")
        self._lbl_topbar_subtitle = ctk.CTkLabel(
            left, text="Gestion de pedidos · WhatsApp Business",
            font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY)
        self._lbl_topbar_subtitle.pack(anchor="w")

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        today_str = datetime.now().strftime("%d/%m/%Y")
        ctk.CTkLabel(right, text=today_str, font=ctk.CTkFont(size=11),
                     text_color=TEXT_SECONDARY).pack(side="right", padx=(16, 0))
        ctk.CTkButton(right, text="📄  PDF", width=100, height=34,
                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                       font=ctk.CTkFont(family=EF, size=11, weight="bold"), corner_radius=8,
                       command=self._export_pdf).pack(side="right", padx=4)
        ctk.CTkButton(right, text="📊  Excel", width=108, height=34,
                       fg_color=SUCCESS, hover_color="#059669",
                       font=ctk.CTkFont(family=EF, size=11, weight="bold"), corner_radius=8,
                       command=self._export_excel).pack(side="right")
        ctk.CTkFrame(bar, height=1, fg_color=BORDER).pack(fill="x")

    # ──────────────────────────────────────────────────────────────────────────
    # PAGINA: PANEL
    # ──────────────────────────────────────────────────────────────────────────
    def _build_panel_page(self, container):
        self._panel_page = tk.Frame(container, bg=CONTENT_BG)
        self._panel_page.grid_columnconfigure(0, weight=1)
        self._panel_page.grid_rowconfigure(1, weight=1)
        self._build_kpi_row(self._panel_page)
        main = tk.Frame(self._panel_page, bg=CONTENT_BG)
        main.grid(row=1, column=0, sticky="nsew", padx=24, pady=(12, 20))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        self._build_filter_bar(main)
        self._build_table(main)

    def _build_kpi_row(self, parent):
        wrap = tk.Frame(parent, bg=CONTENT_BG)
        wrap.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        self.kpi_vars = {
            "total":      tk.StringVar(value="$0.00"),
            "count":      tk.StringVar(value="0"),
            "completado": tk.StringVar(value="0"),
            "pendiente":  tk.StringVar(value="0"),
        }
        for i, (label, key, color, light, icon) in enumerate([
            ("Total Facturado",  "total",      PRIMARY,  "#EEF2FF",     "💰"),
            ("Órdenes Totales",  "count",      WA_DARK,  "#ECFDF5",     "📦"),
            ("Completadas",      "completado", SUCCESS,  SUCCESS_LIGHT, "✅"),
            ("Pendientes",       "pendiente",  WARNING,  WARNING_LIGHT, "⏳"),
        ]):
            card = tk.Frame(wrap, bg=CARD_BG,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", expand=True, fill="x",
                      padx=(0, 14) if i < 3 else 0)
            inner = tk.Frame(card, bg=CARD_BG)
            inner.pack(padx=18, pady=16, fill="x")
            top = tk.Frame(inner, bg=CARD_BG)
            top.pack(fill="x")
            tk.Label(top, text=label, bg=CARD_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 10)).pack(side="left")
            tk.Label(top, text=f" {icon} ", bg=light,
                     font=(EF, 13), padx=4, pady=2).pack(side="right")
            tk.Label(inner, textvariable=self.kpi_vars[key],
                     bg=CARD_BG, fg=color,
                     font=("Segoe UI", 28, "bold")).pack(anchor="w", pady=(8, 0))

    def _build_filter_bar(self, parent):
        card = tk.Frame(parent, bg=CARD_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        row = tk.Frame(card, bg=CARD_BG)
        row.pack(padx=20, pady=12, fill="x")

        period = tk.Frame(row, bg=CARD_BG)
        period.pack(side="left")
        tk.Label(period, text="Periodo", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        date_row = tk.Frame(period, bg=CARD_BG)
        date_row.pack()

        def _lbl(p, t):
            tk.Label(p, text=t, bg=CARD_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))

        _lbl(date_row, "Desde")
        self.entry_from = ctk.CTkButton(
            date_row, text=f"{date.today().year}-01-01",
            width=130, height=32, anchor="w",
            fg_color=CONTENT_BG, hover_color=BORDER,
            text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=lambda: self._open_date_picker("from"))
        self.entry_from.pack(side="left", padx=(0, 14))

        _lbl(date_row, "Hasta")
        self.entry_to = ctk.CTkButton(
            date_row, text=date.today().isoformat(),
            width=130, height=32, anchor="w",
            fg_color=CONTENT_BG, hover_color=BORDER,
            text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=lambda: self._open_date_picker("to"))
        self.entry_to.pack(side="left", padx=(0, 12))
        ctk.CTkButton(date_row, text="Filtrar", width=82, height=32,
                       fg_color=TEXT_PRIMARY, hover_color=SIDEBAR_BG,
                       font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                       command=self._apply_filter).pack(side="left")

        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=24, pady=2)

        month_sec = tk.Frame(row, bg=CARD_BG)
        month_sec.pack(side="left")
        tk.Label(month_sec, text="Filtro rapido", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        month_row = tk.Frame(month_sec, bg=CARD_BG)
        month_row.pack()
        now = date.today()
        self._mes_var  = tk.StringVar(value=MESES[now.month - 1])
        self._anio_var = tk.StringVar(value=str(now.year))
        ctk.CTkComboBox(month_row, values=MESES, variable=self._mes_var,
                         width=148, height=32, font=ctk.CTkFont(size=11),
                         fg_color=CONTENT_BG, border_color=BORDER,
                         button_color="#CBD5E1", button_hover_color=BORDER,
                         dropdown_fg_color=CARD_BG, dropdown_text_color=TEXT_PRIMARY,
                         dropdown_hover_color="#EEF2FF", text_color=TEXT_PRIMARY,
                         corner_radius=6, state="readonly").pack(side="left", padx=(0, 8))
        years = [str(y) for y in range(now.year, now.year - 5, -1)]
        ctk.CTkComboBox(month_row, values=years, variable=self._anio_var,
                         width=88, height=32, font=ctk.CTkFont(size=11),
                         fg_color=CONTENT_BG, border_color=BORDER,
                         button_color="#CBD5E1", button_hover_color=BORDER,
                         dropdown_fg_color=CARD_BG, dropdown_text_color=TEXT_PRIMARY,
                         dropdown_hover_color="#EEF2FF", text_color=TEXT_PRIMARY,
                         corner_radius=6, state="readonly").pack(side="left", padx=(0, 10))
        ctk.CTkButton(month_row, text="Ir", width=50, height=32,
                       fg_color=SIDEBAR_SECTION, hover_color=SIDEBAR_BG,
                       font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                       command=self._filter_by_month).pack(side="left")

    def _build_table(self, parent):
        card = tk.Frame(parent, bg=CARD_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 0))
        tk.Label(hdr, text="Ordenes", bg=CARD_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.lbl_count = tk.Label(hdr, text="", bg=CARD_BG, fg=TEXT_SECONDARY,
                                   font=("Segoe UI", 10))
        self.lbl_count.pack(side="left", padx=(12, 0))
        tk.Frame(card, bg=BORDER, height=1).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(52, 0))

        sty = ttk.Style()
        sty.theme_use("clam")
        sty.configure("WBS.Treeview",
                       background=CARD_BG, fieldbackground=CARD_BG,
                       rowheight=38, font=("Segoe UI", 10), borderwidth=0, relief="flat")
        sty.configure("WBS.Treeview.Heading",
                       background="#F8FAFC", foreground=TEXT_SECONDARY,
                       font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0, padding=10)
        sty.map("WBS.Treeview",
                background=[("selected", "#EEF2FF")], foreground=[("selected", PRIMARY)])
        sty.map("WBS.Treeview.Heading", background=[("active", BORDER)])
        sty.layout("WBS.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        cols = ("ID", "Cliente", "Producto", "Fecha", "Monto", "Estado")
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                  style="WBS.Treeview", selectmode="extended")
        for col, w, anch in [("ID",110,"w"),("Cliente",190,"w"),("Producto",210,"w"),
                              ("Fecha",110,"center"),("Monto",110,"e"),("Estado",120,"center")]:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=anch, minwidth=60)
        self.tree.tag_configure("completado", foreground="#065F46", background="#F0FDF4")
        self.tree.tag_configure("pendiente",  foreground="#92400E", background="#FFFBEB")
        self.tree.tag_configure("cancelado",  foreground="#991B1B", background="#FFF1F2")
        self.tree.tag_configure("error",      foreground=TEXT_MUTED)
        self.tree.tag_configure("alt_row",    background="#FAFAFA")
        sb2 = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb2.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb2.grid(row=1, column=1, sticky="ns")

    # ──────────────────────────────────────────────────────────────────────────
    # PAGINA: ANALITICA
    # ──────────────────────────────────────────────────────────────────────────
    def _build_analytics_page(self, container):
        self._analytics_page = tk.Frame(container, bg=CONTENT_BG)
        self._analytics_page.grid_columnconfigure(0, weight=1)
        self._analytics_page.grid_rowconfigure(2, weight=1)
        self._build_analytics_filter(self._analytics_page)
        self._build_analytics_kpis(self._analytics_page)
        self._build_analytics_charts(self._analytics_page)

    def _build_analytics_filter(self, parent):
        card = tk.Frame(parent, bg=CARD_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        row = tk.Frame(card, bg=CARD_BG)
        row.pack(padx=20, pady=12, fill="x")

        tk.Label(row, text="Periodo de analisis", bg=CARD_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=18, pady=2)
        now = date.today()
        self._an_year_var  = tk.StringVar(value=str(now.year))
        self._an_month_var = tk.StringVar(value="Todos")

        tk.Label(row, text="Anio:", bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        years = [str(y) for y in range(now.year, now.year - 6, -1)]
        ctk.CTkComboBox(row, values=years, variable=self._an_year_var,
                         width=90, height=32, font=ctk.CTkFont(size=11),
                         fg_color=CONTENT_BG, border_color=BORDER,
                         button_color="#CBD5E1", button_hover_color=BORDER,
                         dropdown_fg_color=CARD_BG, dropdown_text_color=TEXT_PRIMARY,
                         dropdown_hover_color="#EEF2FF", text_color=TEXT_PRIMARY,
                         corner_radius=6, state="readonly").pack(side="left", padx=(0, 14))

        tk.Label(row, text="Mes:", bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        ctk.CTkComboBox(row, values=["Todos"] + MESES, variable=self._an_month_var,
                         width=140, height=32, font=ctk.CTkFont(size=11),
                         fg_color=CONTENT_BG, border_color=BORDER,
                         button_color="#CBD5E1", button_hover_color=BORDER,
                         dropdown_fg_color=CARD_BG, dropdown_text_color=TEXT_PRIMARY,
                         dropdown_hover_color="#EEF2FF", text_color=TEXT_PRIMARY,
                         corner_radius=6, state="readonly").pack(side="left", padx=(0, 14))

        ctk.CTkButton(row, text="Actualizar", width=100, height=32,
                       fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                       font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6,
                       command=self._refresh_analytics).pack(side="left")
        self._an_lbl_info = tk.Label(row, text="", bg=CARD_BG, fg=TEXT_MUTED,
                                      font=("Segoe UI", 9))
        self._an_lbl_info.pack(side="right")

    def _build_analytics_kpis(self, parent):
        wrap = tk.Frame(parent, bg=CONTENT_BG)
        wrap.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))
        self._an_kpi_vars = {
            "ticket_prom":   tk.StringVar(value="$0.00"),
            "prod_estrella": tk.StringVar(value="---"),
            "mejor_cliente": tk.StringVar(value="---"),
            "tasa_comp":     tk.StringVar(value="0%"),
        }
        for i, (label, key, color, light) in enumerate([
            ("Ticket Promedio",     "ticket_prom",   PRIMARY,  "#EEF2FF"),
            ("Producto Estrella",   "prod_estrella", SUCCESS,  SUCCESS_LIGHT),
            ("Mejor Cliente",       "mejor_cliente", WA_DARK,  "#ECFDF5"),
            ("Tasa de Completadas", "tasa_comp",     WARNING,  WARNING_LIGHT),
        ]):
            card = tk.Frame(wrap, bg=CARD_BG,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", expand=True, fill="x",
                      padx=(0, 14) if i < 3 else 0)
            inner = tk.Frame(card, bg=CARD_BG)
            inner.pack(padx=18, pady=14, fill="x")
            tk.Label(inner, text=label, bg=CARD_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 10)).pack(anchor="w")
            tk.Label(inner, textvariable=self._an_kpi_vars[key],
                     bg=CARD_BG, fg=color,
                     font=("Segoe UI", 17, "bold"),
                     wraplength=160).pack(anchor="w", pady=(6, 0))

    def _build_analytics_charts(self, parent):
        outer = tk.Frame(parent, bg=CONTENT_BG)
        outer.grid(row=2, column=0, sticky="nsew", padx=24, pady=(14, 20))
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=3)
        outer.grid_rowconfigure(1, weight=4)

        self._chart_monthly = tk.Frame(outer, bg=CARD_BG,
                                        highlightthickness=1, highlightbackground=BORDER)
        self._chart_monthly.grid(row=0, column=0, sticky="nsew", pady=(0, 12))

        bottom = tk.Frame(outer, bg=CONTENT_BG)
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.grid_columnconfigure(0, weight=4)
        bottom.grid_columnconfigure(1, weight=6)
        bottom.grid_rowconfigure(0, weight=1)

        self._chart_pie = tk.Frame(bottom, bg=CARD_BG,
                                    highlightthickness=1, highlightbackground=BORDER)
        self._chart_pie.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self._chart_products = tk.Frame(bottom, bg=CARD_BG,
                                         highlightthickness=1, highlightbackground=BORDER)
        self._chart_products.grid(row=0, column=1, sticky="nsew")

    # ──────────────────────────────────────────────────────────────────────────
    # LOGICA DE ANALITICA
    # ──────────────────────────────────────────────────────────────────────────
    def _get_analytics_orders(self) -> list:
        try:
            year = int(self._an_year_var.get())
        except (ValueError, AttributeError):
            logger.warning("[ANALYTICS] Año inválido en filtro de analítica")
            return []
        month_str = self._an_month_var.get()
        prefix = f"{year:04d}"
        if month_str != "Todos":
            m_num  = MESES.index(month_str) + 1
            prefix = f"{year:04d}-{m_num:02d}"
        analytics_orders = [o for o in self.orders if o["fecha"].startswith(prefix)]
        logger.info(
            "[ANALYTICS] Scope=%s total_orders=%s analytics_orders=%s",
            prefix, len(self.orders), len(analytics_orders))
        return analytics_orders

    def _refresh_analytics(self):
        if not MATPLOTLIB_OK:
            self._show_no_matplotlib_msg()
            return
        orders = self._get_analytics_orders()
        self._validate_orders_for_analytics(orders)
        year   = int(self._an_year_var.get())
        total_rev = sum(o["monto"] for o in orders if o.get("estado") == "Completado")
        logger.info("[ANALYTICS] Refresh year=%s count=%s revenue=%.2f", year, len(orders), total_rev)
        self._an_lbl_info.config(
            text=f"{len(orders)} ordenes  ·  ${total_rev:,.2f} total")
        self._refresh_analytics_kpis(orders)
        self._draw_monthly_revenue(orders, year)
        self._draw_status_pie(orders)
        self._draw_top_products(orders)

    def _validate_orders_for_analytics(self, orders: list):
        """Traza consistencia entre pedidos usados y métricas calculables."""
        if not orders:
            return
        missing_required = 0
        invalid_amount = 0
        seen_ids = set()
        duplicate_ids = 0

        for o in orders:
            if not all(k in o for k in ("id", "fecha", "monto", "estado", "cliente", "producto")):
                missing_required += 1
            try:
                float(o.get("monto", 0.0))
            except (TypeError, ValueError):
                invalid_amount += 1

            oid = o.get("id")
            if oid in seen_ids:
                duplicate_ids += 1
            else:
                seen_ids.add(oid)

        logger.info(
            "[ANALYTICS][RELATION] pedidos=%s faltantes=%s montos_invalidos=%s ids_duplicados=%s",
            len(orders), missing_required, invalid_amount, duplicate_ids)

    def _refresh_analytics_kpis(self, orders: list):
        if not orders:
            for k in self._an_kpi_vars:
                self._an_kpi_vars[k].set("Sin datos")
            logger.info("[ANALYTICS] KPIs sin datos para el filtro actual")
            return
        complt = sum(1 for o in orders if o.get("estado") == "Completado")
        total  = sum(o["monto"] for o in orders if o.get("estado") == "Completado")
        count  = len(orders)
        self._an_kpi_vars["ticket_prom"].set(f"${total / complt:,.2f}" if complt else "$0.00")
        rev_prod = defaultdict(float)
        for o in orders:
            if o.get("estado") == "Completado":
                rev_prod[o["producto"]] += o["monto"]
        if rev_prod:
            bp = max(rev_prod, key=rev_prod.__getitem__)
            self._an_kpi_vars["prod_estrella"].set(bp[:22] + "..." if len(bp) > 22 else bp)
        rev_cli = defaultdict(float)
        for o in orders:
            if o.get("estado") == "Completado":
                rev_cli[o["cliente"]] += o["monto"]
        if rev_cli:
            bc = max(rev_cli, key=rev_cli.__getitem__)
            self._an_kpi_vars["mejor_cliente"].set(bc[:22] + "..." if len(bc) > 22 else bc)
        tasa = (complt / count * 100) if count else 0
        self._an_kpi_vars["tasa_comp"].set(f"{tasa:.1f}%")
        logger.info(
            "[ANALYTICS] KPIs count=%s total=%.2f completadas=%s tasa=%.1f%%",
            count, total, complt, tasa)

    def _draw_monthly_revenue(self, orders: list, year: int):
        self._clear_frame(self._chart_monthly)
        monthly     = defaultdict(float)
        monthly_cnt = defaultdict(int)
        for o in orders:
            if o["fecha"].startswith(f"{year:04d}") and o.get("estado") == "Completado":
                m = int(o["fecha"][5:7])
                monthly[m]     += o["monto"]
                monthly_cnt[m] += 1
        revenues = [monthly.get(m, 0.0)    for m in range(1, 13)]
        counts   = [monthly_cnt.get(m, 0)   for m in range(1, 13)]
        max_rev  = max(revenues) if any(revenues) else 1

        hdr = tk.Frame(self._chart_monthly, bg=CARD_BG)
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text=f"Ventas mensuales - {year}",
                 bg=CARD_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(hdr, text=f"  Total: ${sum(revenues):,.2f}",
                 bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))

        fig = Figure(facecolor=CARD_BG)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.85, bottom=0.16)
        ax  = fig.add_subplot(111)
        bar_colors = [PRIMARY if r > 0 else "#E2E8F0" for r in revenues]
        bars = ax.bar(range(12), revenues, width=0.6, zorder=2,
                      color=bar_colors, alpha=0.88)
        ax.set_xticks(range(12))
        ax.set_xticklabels(MESES_CORTOS, fontsize=9, color=TEXT_SECONDARY)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.tick_params(axis="y", labelsize=9, labelcolor=TEXT_SECONDARY)
        ax.set_facecolor(CARD_BG)
        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(BORDER)
        ax.yaxis.grid(True, color=BORDER, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for bar, rev in zip(bars, revenues):
            if rev > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        rev + max_rev * 0.015,
                        f"${rev:,.0f}", ha="center", va="bottom",
                        fontsize=7.5, color=TEXT_PRIMARY, fontweight="bold")

        canvas = FigureCanvasTkAgg(fig, master=self._chart_monthly)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(4, 10))

    def _draw_status_pie(self, orders: list):
        self._clear_frame(self._chart_pie)
        cnt_map = {"Completado": 0, "Pendiente": 0, "Cancelado": 0, "Desconocido": 0}
        for o in orders:
            key = o["estado"] if o["estado"] in cnt_map else "Desconocido"
            cnt_map[key] += 1
        labels     = [k for k, v in cnt_map.items() if v > 0]
        sizes      = [v for v in cnt_map.values()  if v > 0]
        pie_colors = {
            "Completado": SUCCESS,
            "Pendiente": WARNING,
            "Cancelado": DANGER,
            "Desconocido": TEXT_MUTED,
        }

        hdr = tk.Frame(self._chart_pie, bg=CARD_BG)
        hdr.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(hdr, text="Distribucion por estado",
                 bg=CARD_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        if not sizes:
            tk.Label(self._chart_pie, text="Sin datos",
                     bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 11)).pack(expand=True)
            return

        fig = Figure(facecolor=CARD_BG)
        fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05)
        ax  = fig.add_subplot(111)
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels,
            colors=[pie_colors[l] for l in labels],
            autopct=lambda p: f"{p:.1f}%\n({int(round(p * sum(sizes) / 100))})",
            startangle=90, pctdistance=0.72,
            wedgeprops={"linewidth": 2, "edgecolor": CARD_BG})
        for t in texts:
            t.set_fontsize(9); t.set_color(TEXT_PRIMARY)
        for at in autotexts:
            at.set_fontsize(8.5); at.set_color("white"); at.set_fontweight("bold")
        ax.set_facecolor(CARD_BG)

        canvas = FigureCanvasTkAgg(fig, master=self._chart_pie)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(4, 10))

    def _draw_top_products(self, orders: list):
        self._clear_frame(self._chart_products)
        rev_prod = defaultdict(float)
        for o in orders:
            if o.get("estado") == "Completado":
                rev_prod[o["producto"]] += o["monto"]
        top5 = sorted(rev_prod.items(), key=lambda x: x[1], reverse=True)[:5]

        hdr = tk.Frame(self._chart_products, bg=CARD_BG)
        hdr.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(hdr, text="Top 5 productos por ingreso",
                 bg=CARD_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        if not top5:
            tk.Label(self._chart_products, text="Sin datos",
                     bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 11)).pack(expand=True)
            return

        names  = [p[:28] + "..." if len(p) > 28 else p for p, _ in top5]
        values = [v for _, v in top5]
        max_v  = max(values) if values else 1

        fig = Figure(facecolor=CARD_BG)
        fig.subplots_adjust(left=0.30, right=0.93, top=0.90, bottom=0.10)
        ax  = fig.add_subplot(111)
        bars = ax.barh(range(len(names)), values, height=0.55, zorder=2,
                       color=CHART_COLORS[:len(names)], alpha=0.88)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=9.5, color=TEXT_PRIMARY)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.tick_params(axis="x", labelsize=9, labelcolor=TEXT_SECONDARY)
        ax.set_facecolor(CARD_BG)
        for spine in ["top", "right", "bottom"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color(BORDER)
        ax.xaxis.grid(True, color=BORDER, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for bar, val in zip(bars, values):
            ax.text(val + max_v * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"${val:,.0f}", va="center",
                    fontsize=8.5, color=TEXT_PRIMARY, fontweight="bold")

        canvas = FigureCanvasTkAgg(fig, master=self._chart_products)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(4, 10))

    def _show_no_matplotlib_msg(self):
        for frame in [self._chart_monthly, self._chart_pie, self._chart_products]:
            self._clear_frame(frame)
            tk.Label(frame,
                     text="Instala matplotlib:\npip install matplotlib",
                     bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 11),
                     justify="center").pack(expand=True)

    @staticmethod
    def _clear_frame(frame: tk.Frame):
        for w in frame.winfo_children():
            w.destroy()

    # ──────────────────────────────────────────────────────────────────────────
    # STATUS BAR
    # ──────────────────────────────────────────────────────────────────────────
    def _build_statusbar(self, parent):
        bar = tk.Frame(parent, bg=CARD_BG, height=30)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")
        self._lbl_statusbar = tk.Label(bar, text="Listo", bg=CARD_BG,
                                        fg=TEXT_MUTED, font=("Segoe UI", 9))
        self._lbl_statusbar.pack(side="left", padx=16, pady=4)

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _set_status_text(self, text: str):
        self.lbl_update.configure(text=text)
        self._lbl_statusbar.config(text=text)

    def _set_connection_state(self, state: str):
        if state == "connected":
            self._lbl_dot.configure(text_color=WA_GREEN)
            self._lbl_conn_title.configure(text="Conectado")
        elif state == "waiting":
            self._lbl_dot.configure(text_color=WARNING)
            self._lbl_conn_title.configure(text="Esperando QR...")
        else:
            self._lbl_dot.configure(text_color=DANGER)
            self._lbl_conn_title.configure(text="Desconectado")

    def _dispose_driver(self):
        driver = None
        with self._driver_lock:
            if self.driver:
                driver = self.driver
                self.driver = None
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    def _is_whatsapp_linked(self) -> bool:
        with self._driver_lock:
            if not self.driver:
                return False
            try:
                return bool(self.driver.execute_script("""
                    const text = (document.body.innerText || "").toLowerCase();
                    const connectedSelectors = [
                        '[data-testid="menu-bar-item-business-tools"]',
                        '[data-testid="menu-bar-menu"]',
                        '#side',
                        '#main',
                        'header',
                        'aside',
                        'div[contenteditable="true"][role="textbox"]',
                        'div[role="textbox"][contenteditable="true"]',
                        'button[aria-label*="Attach"]',
                        'button[aria-label*="Adjuntar"]',
                        'button[title*="New chat"]',
                        'button[title*="Nuevo chat"]',
                        'nav'
                    ];
                    const hasConnectedUi = connectedSelectors.some(
                        selector => document.querySelector(selector)
                    );
                    const connectedTexts = [
                        "chats",
                        "archived",
                        "herramientas de empresa",
                        "business tools",
                        "orders",
                        "pedidos"
                    ];
                    const hasConnectedText = connectedTexts.some(
                        token => text.includes(token)
                    );
                    return hasConnectedUi || hasConnectedText;
                """))
            except Exception:
                return False

    # ──────────────────────────────────────────────────────────────────────────
    # CONEXION
    # ──────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────
    # OVERLAY QR
    # ──────────────────────────────────────────────────────────────────────────
    def _show_qr_overlay(self):
        self._qr_active   = False
        self._qr_after_id = None
        self._qr_photo    = None
        self._qr_page_photo = None

        self._qr_overlay = ctk.CTkFrame(self, fg_color="#0F172A", corner_radius=0)
        self._qr_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._qr_overlay.lift()

        card = ctk.CTkFrame(self._qr_overlay, fg_color=CARD_BG,
                            corner_radius=20, width=460, height=650)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="WBS",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=WA_GREEN).pack(pady=(28, 0))
        ctk.CTkLabel(card, text="Conectar WhatsApp",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT_TITLE).pack(pady=(6, 2))
        ctk.CTkLabel(card,
                     text="Abre WhatsApp → Menú → Dispositivos vinculados\n→ Vincular dispositivo → Escanea el QR",
                     font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY,
                     justify="center").pack(pady=(0, 14))

        self._qr_status_label = ctk.CTkLabel(
            card,
            text="Iniciando navegador interno...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self._qr_status_label.pack(pady=(0, 10))

        qr_frame = ctk.CTkFrame(card, fg_color=CONTENT_BG, corner_radius=16,
                                width=320, height=320)
        qr_frame.pack(padx=28, pady=(0, 10))
        qr_frame.pack_propagate(False)

        self._qr_img_label = tk.Label(
            qr_frame,
            bg=CONTENT_BG,
            text="Cargando código QR...",
            font=("Segoe UI", 12),
            fg=TEXT_MUTED,
            justify="center",
        )
        self._qr_img_label.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card,
                     text="Vista previa de WhatsApp Web",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(pady=(0, 6))

        preview_frame = ctk.CTkFrame(card, fg_color=CONTENT_BG, corner_radius=14,
                                     width=360, height=110)
        preview_frame.pack(padx=28, pady=(0, 12))
        preview_frame.pack_propagate(False)

        self._qr_preview_label = tk.Label(
            preview_frame,
            bg=CONTENT_BG,
            text="Preparando vista previa...",
            font=("Segoe UI", 10),
            fg=TEXT_MUTED,
            justify="center",
        )
        self._qr_preview_label.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(card, text="Cancelar",
                      fg_color="transparent", hover_color=CONTENT_BG,
                      text_color=TEXT_SECONDARY,
                      border_width=1, border_color=BORDER,
                      height=36, corner_radius=8,
                      command=self._cancel_connect).pack(
            pady=(14, 26), padx=40, fill="x")

    def _hide_qr_overlay(self):
        self._stop_qr_refresh()
        if hasattr(self, "_qr_overlay") and self._qr_overlay.winfo_exists():
            self._qr_overlay.destroy()

    def _cancel_connect(self):
        self._hide_qr_overlay()
        self._dispose_driver()
        self._reset_connect_btn()

    def _start_qr_refresh(self):
        self._qr_active = True
        self._do_qr_refresh()

    def _stop_qr_refresh(self):
        self._qr_active = False
        if hasattr(self, "_qr_after_id") and self._qr_after_id:
            self.after_cancel(self._qr_after_id)
            self._qr_after_id = None

    def _do_qr_refresh(self):
        if not self._qr_active or not self.driver:
            return

        def capture():
            """Corre en hilo secundario. Devuelve (qr_png, full_png, crop_box)."""
            with self._driver_lock:
                if not self.driver:
                    return None, None, None

                qr_png = None
                selectors = [
                    '[data-testid="qrcode"]',
                    '[data-testid="qrcode"] canvas',
                    'canvas[aria-label*="Scan"]',
                    'div[data-ref] canvas',
                    '.landing-main canvas',
                    'canvas',
                ]
                for sel in selectors:
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if el.size.get("width", 0) >= 140 and el.size.get("height", 0) >= 140:
                            qr_png = el.screenshot_as_png
                            if qr_png:
                                break
                    except Exception:
                        continue

                rect = None
                dpr = 1
                try:
                    rect = self.driver.execute_script("""
                        var qr = document.querySelector('canvas[aria-label*="Scan"], div[data-ref] canvas, [data-testid="qrcode"], [data-testid="qrcode"] canvas');
                        if (!qr) {
                            var all = document.querySelectorAll('img, canvas');
                            for (var el of all) {
                                var r = el.getBoundingClientRect();
                                if (r.width >= 150 && r.height >= 150 &&
                                    Math.abs(r.width - r.height) < 40 &&
                                    r.x >= 0 && r.y >= 0) {
                                    qr = el;
                                    break;
                                }
                            }
                        }
                        if (!qr) return null;
                        var r = qr.getBoundingClientRect();
                        return {x: r.x, y: r.y, w: r.width, h: r.height};
                    """)
                    dpr = self.driver.execute_script(
                        "return window.devicePixelRatio || 1") or 1
                except Exception:
                    pass

                try:
                    full_png = self.driver.get_screenshot_as_png()
                except Exception:
                    full_png = None

            if rect:
                x1 = max(0, int(rect["x"] * dpr) - 8)
                y1 = max(0, int(rect["y"] * dpr) - 8)
                x2 = x1 + int(rect["w"] * dpr) + 16
                y2 = y1 + int(rect["h"] * dpr) + 16
                return qr_png, full_png, (x1, y1, x2, y2)

            return qr_png, full_png, None

        def on_result(result):
            """Corre en el hilo principal (after)."""
            qr_png, page_png, crop_box, linked = result
            if not self._qr_active:
                return
            if (qr_png or page_png) and PIL_OK:
                try:
                    if qr_png:
                        qr_img = Image.open(io.BytesIO(qr_png))
                    else:
                        qr_img = Image.open(io.BytesIO(page_png))
                        if crop_box:
                            qr_img = qr_img.crop(crop_box)
                        else:
                            w, h = qr_img.size
                            qr_img = qr_img.crop((
                                int(w * 0.57), int(h * 0.44),
                                int(w * 0.94), int(h * 0.98),
                            ))
                    qr_img = qr_img.resize((280, 280), Image.LANCZOS)
                    self._qr_photo = ImageTk.PhotoImage(qr_img)
                    if hasattr(self, "_qr_img_label") and \
                       self._qr_img_label.winfo_exists():
                        self._qr_img_label.configure(
                            image=self._qr_photo, text="", width=280, height=280)

                    if page_png and hasattr(self, "_qr_preview_label") and \
                       self._qr_preview_label.winfo_exists():
                        page_img = Image.open(io.BytesIO(page_png))
                        page_img.thumbnail((330, 100), Image.LANCZOS)
                        self._qr_page_photo = ImageTk.PhotoImage(page_img)
                        self._qr_preview_label.configure(
                            image=self._qr_page_photo, text="", width=330, height=100)

                    if hasattr(self, "_qr_status_label") and \
                       self._qr_status_label.winfo_exists():
                        self._qr_status_label.configure(
                            text="Escanea este QR. El navegador corre dentro de la app.")
                except Exception as exc:
                    if hasattr(self, "_qr_status_label") and \
                       self._qr_status_label.winfo_exists():
                        self._qr_status_label.configure(
                            text=f"Esperando QR... ({type(exc).__name__})")
            elif hasattr(self, "_qr_status_label") and \
                 self._qr_status_label.winfo_exists():
                self._qr_status_label.configure(
                    text="Esperando que WhatsApp genere el QR...")

            if not PIL_OK and hasattr(self, "_qr_img_label") and \
               self._qr_img_label.winfo_exists():
                self._qr_img_label.configure(
                    text="Instala Pillow para mostrar el QR:\npip install Pillow")
            if self._qr_active:
                self._qr_after_id = self.after(2500, self._do_qr_refresh)

        def run():
            qr_png, page_png, crop_box = capture()
            linked = self._is_whatsapp_linked()
            result = (qr_png, page_png, crop_box, linked)
            self.after(0, lambda: on_result(result))

        threading.Thread(target=run, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # CONEXION
    # ──────────────────────────────────────────────────────────────────────────
    def _connect(self):
        self.btn_connect.configure(state="disabled", text="Conectando dentro de la app...")
        self._show_qr_overlay()
        threading.Thread(target=self._open_whatsapp, daemon=True).start()

    def _sync(self):
        self.btn_sync.configure(state="disabled", text="Sincronizando...")
        self.btn_sync_auto.configure(state="disabled")
        threading.Thread(target=self._do_sync, daemon=True).start()

    def _toggle_auto_sync(self):
        self.is_auto_sync = not self.is_auto_sync
        if self.is_auto_sync:
            self.btn_sync_auto.configure(text="⏹️  Detener Sincronización Automática", fg_color=DANGER, hover_color="#DC2626")
            self.btn_sync.configure(state="disabled")
            threading.Thread(target=self._auto_sync_loop, daemon=True).start()
        else:
            self.btn_sync_auto.configure(text="🤖  Sincronización Automática", fg_color="#8B5CF6", hover_color="#7C3AED", state="disabled")
            self.btn_sync.configure(state="disabled")
            
    def _auto_sync_loop(self):
        while self.is_auto_sync and self.connected and self.driver:
            self._do_sync()
            if self.is_auto_sync:
                self._set_status_text("⏳ Esperando para siguiente ciclo automático...")
                time.sleep(5) # Pequeña pausa entre ciclos para no saturar CPU/Navegador

        # Cuando el ciclo termina o se desactiva
        self.after(0, lambda: self.btn_sync_auto.configure(state="normal", text="🤖  Sincronización Automática", fg_color="#8B5CF6", hover_color="#7C3AED"))
        self.after(0, lambda: self.btn_sync.configure(state="normal", text="🔄  Sincronización Manual"))
        self.after(0, lambda: self._set_status_text("Automático detenido. Sincronización manual disponible."))

    def _do_sync(self):
        """Realiza sincronización manual de órdenes."""
        try:
            self._set_status_text("⏳ Iniciando sincronización...")
            logger.info("[SYNC] Inicio sincronización manual")
            
            if not self.driver or not self.connected:
                self.after(0, lambda: messagebox.showwarning(
                    "No conectado",
                    "Primero debes conectar tu cuenta de WhatsApp Business"))
                return
            
            scraper = OrderScraper(
                self.driver,
                on_status=lambda msg: self.after(
                    0, lambda m=msg: self._set_status_text(m)))
            
            new_orders = scraper.fetch()
            
            if not new_orders:
                diag = getattr(scraper, "last_run_diagnostics", {}) or {}
                dstatus = diag.get("status", "unknown")
                history = (diag.get("history") or {})
                hstatus = history.get("status", "unknown")
                h_initial = int(history.get("new_orders_visible_initial", 0) or 0)
                h_hist = int(history.get("historical_orders_found", 0) or 0)

                logger_msg = f"[SYNC] Sin órdenes. diagnostics={diag}"
                import logging
                logging.warning(logger_msg)

                if dstatus in ("session_error", "navigation_error"):
                    msg = "⚠️  No se pudo acceder a pedidos por sesión/navegación. Revisa estado de WhatsApp Business."
                elif dstatus == "timeout":
                    msg = "⚠️  Timeout cargando panel de pedidos. Intenta nuevamente."
                elif hstatus == "no_more_history":
                    msg = "ℹ️  No se detectó más historial al hacer scroll. Puede ser límite real de WhatsApp Business para esta sesión."
                elif hstatus == "history_limit_reached":
                    msg = "ℹ️  Se alcanzó el límite configurable de carga de historial. Ajusta HISTORY_MAX_* en config si deseas más alcance."
                elif hstatus == "no_orders_or_access":
                    msg = "⚠️  No hay pedidos visibles o no hay acceso al historial en esta sesión."
                else:
                    msg = "⚠️  No se obtuvieron órdenes. Revisa logs para diagnóstico detallado."

                if h_initial or h_hist:
                    msg = f"{msg} (visibles iniciales: {h_initial}, históricos cargados: {h_hist})"

                self.after(0, lambda m=msg: self._set_status_text(m))
                return
            
            # Sincronizar
            new_c, upd_c = self._db.merge(new_orders)
            logger.info("[SYNC][DB] merge completado nuevas=%s actualizadas=%s", new_c, upd_c)
            
            # Obtener estadísticas
            stats = self._db.get_sync_stats()
            diag = getattr(scraper, "last_run_diagnostics", {}) or {}
            history = (diag.get("history") or {})
            h_initial = int(history.get("new_orders_visible_initial", 0) or 0)
            h_hist = int(history.get("historical_orders_found", 0) or 0)
            h_stop = history.get("stop_reason", "n/a")
            
            # Recargar UI
            all_orders = self._db.get_all()
            self.after(0, lambda: self._load_orders(all_orders))
            self.after(0, self._apply_filter)
            
            ts = datetime.now().strftime("%d/%m/%Y %H:%M")
            msg = (f"✅ Sync exitoso: +{new_c} nuevas, {upd_c} actualizadas "
                     f"· hist inicial: {h_initial}, hist cargado: {h_hist}, stop: {h_stop} "
                     f"· ({stats['with_whatsapp_id']}/{stats['total']} con ID real) · {ts}")
            self.after(0, lambda: self._set_status_text(msg))
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error de sync", str(e)))
            import logging
            logging.exception("Error en _do_sync:")
        finally:
            if not self.is_auto_sync:
                self.after(0, lambda: self.btn_sync.configure(
                    state="normal", text="🔄  Sincronización Manual"))
                self.after(0, lambda: self.btn_sync_auto.configure(state="normal"))

    def _open_whatsapp(self):
        try:
            with self._driver_lock:
                headless_mode = not DEBUG_VISUAL
                logger.info("[SESSION] Abriendo WhatsApp headless=%s (DEBUG_VISUAL=%s)", headless_mode, DEBUG_VISUAL)
                if headless_mode:
                    logger.warning("[SESSION] Modo visual DEBUG desactivado. Para ver el navegador en vivo usa DEBUG=true o DEBUG_VISUAL=true.")
                else:
                    logger.info("[SESSION] Modo visual DEBUG activo: navegador visible y pausas de depuración habilitadas.")
                self.driver, browser = self._browser.build(headless=headless_mode)
                self.driver.set_window_size(1280, 900)
                self.driver.get("https://web.whatsapp.com")
                logger.info("[SESSION] WhatsApp abierto en navegador=%s", browser)

            self.after(0, lambda: self._set_status_text(f"Navegador interno: {browser}"))
            self.after(0, lambda: self._set_connection_state("waiting"))
            self.after(0, self._start_qr_refresh)

            # Esperar hasta 5 minutos a que el usuario escanee el QR.
            # Sólo se hace un page_source cada 3 s para no saturar la conexión
            # con el driver mientras el QR refresh también usa el driver.
            connected = False
            for _ in range(100):
                if not self.driver:
                    return
                try:
                    if self._is_whatsapp_linked():
                        connected = True
                        break
                except Exception:
                    pass
                time.sleep(3)

            if not connected:
                self._dispose_driver()
                self.after(0, self._hide_qr_overlay)
                self.after(0, lambda: messagebox.showwarning(
                    "Tiempo agotado",
                    "No se escaneó el código QR en el tiempo límite."))
                self.after(0, self._reset_connect_btn)
                return

            self.connected = True
            self.after(0, self._hide_qr_overlay)
            self.after(0, self._on_session_linked)
            self.after(0, lambda: self._set_status_text(
                "Sesión vinculada. Iniciando sincronización automática..."))

            self.after(0, lambda: self._on_connected(0, 0))
            self.after(0, self._toggle_auto_sync)
        except Exception as e:
            self.after(0, self._hide_qr_overlay)
            self._dispose_driver()
            self.after(0, lambda: messagebox.showerror("Error de conexion", str(e)))
            self.after(0, self._reset_connect_btn)

    def _on_session_linked(self):
        self._hide_qr_overlay()
        self._set_connection_state("connected")
        self._set_status_text("WhatsApp vinculado. Cargando pedidos...")
        self.btn_connect.pack_forget()
        self.btn_sync.configure(state="disabled", text="Sincronizando...")
        self.btn_sync_auto.configure(state="disabled")
        self.btn_sync.pack(fill="x", pady=(0, 6))
        self.btn_sync_auto.pack(fill="x", pady=(0, 6))
        self.btn_disconnect.pack(fill="x")
        self._apply_filter()

    def _on_connected(self, new_c: int = 0, upd_c: int = 0):
        """Actualiza UI cuando la sesión de WhatsApp está conectada."""
        self._hide_qr_overlay()
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Obtener estadísticas de sincronización
        stats = self._db.get_sync_stats()
        
        msg = (f"✅ Conectado · +{new_c} nuevas, {upd_c} actualizadas "
               f"({stats['with_whatsapp_id']}/{stats['total']} con ID real) · {ts}")
        
        self._set_connection_state("connected")
        self._set_status_text(msg)
        if not self.is_auto_sync:
            self.btn_sync.configure(state="normal", text="🔄  Sincronización Manual")
            self.btn_sync_auto.configure(state="normal")
        self._apply_filter()

    def _disconnect(self):
        self._dispose_driver()
        self.connected = False
        self._set_connection_state("disconnected")
        self._set_status_text("Sin sincronizar")
        self.is_auto_sync = False
        self.btn_disconnect.pack_forget()
        self.btn_sync.pack_forget()
        self.btn_sync_auto.pack_forget()
        self.btn_connect.pack(fill="x", pady=(0, 6))
        self._reset_connect_btn()

    def _reset_connect_btn(self):
        self.btn_connect.configure(state="normal", text="Conectar WhatsApp")

    # ──────────────────────────────────────────────────────────────────────────
    # DATOS Y TABLA
    # ──────────────────────────────────────────────────────────────────────────
    def _load_orders(self, orders: list):
        self.orders = orders
        if orders:
            min_f = min(o.get("fecha", "9999-12-31") for o in orders)
            max_f = max(o.get("fecha", "0000-01-01") for o in orders)
            logger.info("[ORDERS] Carga en memoria: total=%s rango=%s..%s", len(orders), min_f, max_f)
        else:
            logger.info("[ORDERS] Carga en memoria vacía")
        if self._current_page == "analytics":
            self._refresh_analytics()

    def _open_date_picker(self, which: str):
        """Abre un popup de calendario y actualiza el CTkButton correspondiente."""
        btn = self.entry_from if which == "from" else self.entry_to
        try:
            init_date = date.fromisoformat(btn.cget("text"))
        except ValueError:
            init_date = date.today()

        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top.grab_set()

        # Posicionar cerca del botón
        top.update_idletasks()
        bx = btn.winfo_rootx()
        by = btn.winfo_rooty() + btn.winfo_height() + 2
        top.geometry(f"+{bx}+{by}")

        if CAL_OK:
            from tkcalendar import Calendar
            cal = Calendar(
                top, selectmode="day", date_pattern="y-mm-dd",
                year=init_date.year, month=init_date.month, day=init_date.day,
                background=SIDEBAR_BG, foreground="white",
                headersbackground=SIDEBAR_BG, headersforeground="white",
                selectbackground=PRIMARY, selectforeground="white",
                normalbackground=CARD_BG, normalforeground=TEXT_PRIMARY,
                weekendbackground="#F8FAFC", weekendforeground=TEXT_PRIMARY,
                othermonthforeground=TEXT_MUTED, othermonthbackground=CARD_BG,
                bordercolor=BORDER,
            )
            cal.pack(padx=8, pady=8)

            def _pick():
                btn.configure(text=cal.get_date())
                top.destroy()

            ctk.CTkButton(top, text="Seleccionar", height=30,
                          fg_color=PRIMARY, hover_color=SIDEBAR_BG,
                          font=ctk.CTkFont(size=11, weight="bold"),
                          corner_radius=6, command=_pick).pack(pady=(0, 8))
        else:
            # Fallback: entrada de texto simple
            var = tk.StringVar(value=init_date.isoformat())
            ctk.CTkEntry(top, textvariable=var, width=130,
                         font=ctk.CTkFont(size=11)).pack(padx=12, pady=12)

            def _pick():
                btn.configure(text=var.get().strip())
                top.destroy()

            ctk.CTkButton(top, text="Aceptar", height=30, command=_pick,
                          fg_color=PRIMARY, corner_radius=6,
                          font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(0, 10))

    def _get_date_str(self, entry) -> str:
        """Retorna la fecha del widget como string YYYY-MM-DD."""
        if isinstance(entry, ctk.CTkButton):
            return entry.cget("text")
        if CAL_OK and isinstance(entry, DateEntry):
            return entry.get_date().isoformat()
        return entry.get().strip()

    def _apply_filter(self):
        d_from = self._get_date_str(self.entry_from)
        d_to   = self._get_date_str(self.entry_to)
        try:
            datetime.strptime(d_from, "%Y-%m-%d")
            datetime.strptime(d_to,   "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha invalida", "Usa el formato YYYY-MM-DD")
            return
        filtered = [o for o in self.orders if d_from <= o["fecha"] <= d_to]
        logger.info("[ORDERS] Filtro panel aplicado: %s..%s => %s registros", d_from, d_to, len(filtered))
        self._refresh_table(filtered)
        self._refresh_kpis(filtered)
        self.lbl_count.config(
            text=f"· {len(filtered)} resultado(s)   |   Total en BD: {self._db.count()}")

    def _filter_by_month(self):
        try:
            mes  = MESES.index(self._mes_var.get()) + 1
            anio = int(self._anio_var.get())
        except (ValueError, IndexError):
            return
        last_day = calendar.monthrange(anio, mes)[1]
        d_from = f"{anio:04d}-{mes:02d}-01"
        d_to   = f"{anio:04d}-{mes:02d}-{last_day:02d}"
        self.entry_from.configure(text=d_from)
        self.entry_to.configure(text=d_to)
        self._apply_filter()

    def _refresh_table(self, orders: list):
        self.tree.delete(*self.tree.get_children())
        for i, o in enumerate(sorted(orders, key=lambda x: x["fecha"], reverse=True)):
            tag  = o["estado"].lower()
            tags = (tag,) if i % 2 == 0 else (tag, "alt_row")
            self.tree.insert("", "end",
                             values=(o["id"], o["cliente"], o["producto"],
                                     o["fecha"], f"${o['monto']:,.2f}", o["estado"]),
                             tags=tags)

    def _refresh_kpis(self, orders: list):
        total = sum(o["monto"] for o in orders if o.get("estado") == "Completado")
        self.kpi_vars["total"].set(f"${total:,.2f}")
        self.kpi_vars["count"].set(str(len(orders)))
        self.kpi_vars["completado"].set(
            str(sum(1 for o in orders if o["estado"] == "Completado")))
        self.kpi_vars["pendiente"].set(
            str(sum(1 for o in orders if o["estado"] == "Pendiente")))

    def _sort_by(self, col: str):
        col_map = {"ID":"id","Cliente":"cliente","Producto":"producto",
                   "Fecha":"fecha","Monto":"monto","Estado":"estado"}
        key = col_map.get(col, col.lower())
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        d_from = self._get_date_str(self.entry_from)
        d_to   = self._get_date_str(self.entry_to)
        filtered = [o for o in self.orders if d_from <= o["fecha"] <= d_to]
        self._refresh_table(
            sorted(filtered, key=lambda x: x.get(key, ""), reverse=self._sort_rev))

    def _get_filtered_orders(self) -> list:
        d_from = self._get_date_str(self.entry_from)
        d_to   = self._get_date_str(self.entry_to)
        filtered = [o for o in self.orders if d_from <= o["fecha"] <= d_to]
        logger.info("[ORDERS] Dataset exportable: %s..%s => %s registros", d_from, d_to, len(filtered))
        return filtered

    # ──────────────────────────────────────────────────────────────────────────
    # EXPORTACION
    # ──────────────────────────────────────────────────────────────────────────
    def _export_excel(self):
        export_orders = self._get_filtered_orders()
        logger.info("[EXPORT] Excel solicitado con %s órdenes", len(export_orders))
        ok, msg = self._exporter.to_excel(
            export_orders,
            self._get_date_str(self.entry_from),
            self._get_date_str(self.entry_to))
        (messagebox.showinfo if ok else messagebox.showerror)("Excel", msg)

    def _export_pdf(self):
        export_orders = self._get_filtered_orders()
        logger.info("[EXPORT] PDF solicitado con %s órdenes", len(export_orders))
        ok, msg = self._exporter.to_pdf(
            export_orders,
            self._get_date_str(self.entry_from),
            self._get_date_str(self.entry_to))
        (messagebox.showinfo if ok else messagebox.showerror)("PDF", msg)

    # ──────────────────────────────────────────────────────────────────────────
    # PAGINA: REPORTES
    # ──────────────────────────────────────────────────────────────────────────
    def _build_reports_page(self, container):
        self._reports_page = tk.Frame(container, bg=CONTENT_BG)
        self._reports_page.grid_columnconfigure(0, weight=1)
        self._reports_page.grid_rowconfigure(1, weight=1)

        hdr = tk.Frame(self._reports_page, bg=CONTENT_BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Reportes generados",
                 bg=CONTENT_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 18, "bold")).pack(side="left")

        self._reports_scroll = ctk.CTkScrollableFrame(
            self._reports_page, fg_color=CONTENT_BG, corner_radius=0)
        self._reports_scroll.grid(row=1, column=0, sticky="nsew",
                                   padx=24, pady=(0, 20))
        self._reports_scroll.grid_columnconfigure(0, weight=1)

    def _refresh_reports(self):
        if hasattr(self, "_reports_inner") and self._reports_inner.winfo_exists():
            self._reports_inner.destroy()
        self._reports_inner = tk.Frame(self._reports_scroll, bg=CONTENT_BG)
        self._reports_inner.pack(fill="x")
        self._reports_inner.grid_columnconfigure(0, weight=1)

        reports_dir = self._exporter.REPORTS_DIR
        if not os.path.isdir(reports_dir):
            tk.Label(self._reports_inner,
                     text="No hay reportes generados aún.",
                     bg=CONTENT_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 12)).pack(pady=40)
            return

        files = [
            (os.path.getmtime(os.path.join(reports_dir, f)), f,
             os.path.join(reports_dir, f))
            for f in os.listdir(reports_dir)
            if f.lower().endswith((".xlsx", ".pdf"))
        ]
        files.sort(reverse=True)

        if not files:
            tk.Label(self._reports_inner,
                     text="No hay reportes generados aún.",
                     bg=CONTENT_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 12)).pack(pady=40)
            return

        for idx, (mtime, fname, fpath) in enumerate(files):
            self._build_report_item(self._reports_inner, fname, fpath, mtime, idx)

    def _build_report_item(self, parent, fname, fpath, mtime, row_idx):
        card = tk.Frame(parent, bg=CARD_BG,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=row_idx, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)

        icon = "📊" if fname.lower().endswith(".xlsx") else "📄"
        tk.Label(card, text=icon, bg=CARD_BG,
                 font=(EF, 22)).grid(
            row=0, column=0, padx=(20, 16), pady=16, sticky="w")

        info = tk.Frame(card, bg=CARD_BG)
        info.grid(row=0, column=1, sticky="ew", pady=14)
        tk.Label(info, text=fname, bg=CARD_BG, fg=TEXT_TITLE,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ts = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y  %H:%M:%S")
        tk.Label(info, text=f"Generado: {ts}", bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        ctk.CTkButton(
            card, text="⬇  Abrir",
            width=100, height=34,
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
            font=ctk.CTkFont(family=EF, size=11, weight="bold"),
            corner_radius=8,
            command=lambda p=fpath: self._exporter._open_file(p),
        ).grid(row=0, column=2, padx=(12, 20), pady=16)
