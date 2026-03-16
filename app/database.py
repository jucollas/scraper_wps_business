# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# database.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Persistencia local de pedidos usando SQLite."""

import sqlite3
import os
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# La base de datos se guarda junto a los módulos de la app
DB_PATH = Path(__file__).parent / "orders.db"


class Database:
    """
    Maneja el almacenamiento persistente de órdenes en SQLite.
    La tabla usa el ID de WhatsApp como clave primaria para evitar duplicados.
    """

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crea la tabla si no existe."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id        TEXT PRIMARY KEY,
                    cliente   TEXT NOT NULL DEFAULT '',
                    producto  TEXT NOT NULL DEFAULT '',
                    monto     REAL NOT NULL DEFAULT 0.0,
                    fecha     TEXT NOT NULL,
                    estado    TEXT NOT NULL DEFAULT 'Desconocido',
                    synced_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_fecha ON orders(fecha)
            """)
            conn.commit()
        logger.info(f"Base de datos lista: {self.db_path}")

    # ── Escritura ─────────────────────────────────────────────────────────────

    def upsert_orders(self, orders: list[dict]) -> int:
        """
        Inserta o actualiza órdenes. Devuelve el número de registros afectados.
        Si el ID ya existe, actualiza todos los campos excepto el ID.
        """
        if not orders:
            return 0

        with self._connect() as conn:
            affected = 0
            for o in orders:
                conn.execute("""
                    INSERT INTO orders (id, cliente, producto, monto, fecha, estado, synced_at)
                    VALUES (:id, :cliente, :producto, :monto, :fecha, :estado, datetime('now','localtime'))
                    ON CONFLICT(id) DO UPDATE SET
                        cliente   = excluded.cliente,
                        producto  = excluded.producto,
                        monto     = excluded.monto,
                        fecha     = excluded.fecha,
                        estado    = excluded.estado,
                        synced_at = excluded.synced_at
                """, {
                    'id':       o.get('id', ''),
                    'cliente':  o.get('cliente', ''),
                    'producto': o.get('producto', ''),
                    'monto':    float(o.get('monto', 0.0)),
                    'fecha':    o.get('fecha', date.today().isoformat()),
                    'estado':   o.get('estado', 'Desconocido'),
                })
                affected += conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        logger.info(f"upsert_orders: {affected} registro(s) afectado(s)")
        return affected

    def update_estado(self, order_id: str, estado: str):
        """Actualiza el estado de una orden específica."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE orders SET estado = ? WHERE id = ?",
                (estado, order_id))
            conn.commit()

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_all(self) -> list[dict]:
        """Devuelve todas las órdenes ordenadas por fecha descendente."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, cliente, producto, monto, fecha, estado "
                "FROM orders ORDER BY fecha DESC").fetchall()
        return [dict(r) for r in rows]

    def get_by_date_range(self, date_from: str, date_to: str) -> list[dict]:
        """Devuelve órdenes dentro de un rango de fechas (YYYY-MM-DD)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, cliente, producto, monto, fecha, estado "
                "FROM orders WHERE fecha BETWEEN ? AND ? ORDER BY fecha DESC",
                (date_from, date_to)).fetchall()
        return [dict(r) for r in rows]

    def get_by_month(self, year: int, month: int) -> list[dict]:
        """Devuelve órdenes de un mes/año específico."""
        prefix = f"{year:04d}-{month:02d}"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, cliente, producto, monto, fecha, estado "
                "FROM orders WHERE fecha LIKE ? ORDER BY fecha DESC",
                (f"{prefix}%",)).fetchall()
        return [dict(r) for r in rows]

    def get_months(self) -> list[tuple[int, int]]:
        """
        Devuelve lista de (año, mes) con al menos una orden, ordenados desc.
        Útil para poblar el selector de meses en la UI.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT substr(fecha,1,4) AS y, substr(fecha,6,2) AS m "
                "FROM orders ORDER BY y DESC, m DESC").fetchall()
        return [(int(r['y']), int(r['m'])) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    # ── Utilidades ────────────────────────────────────────────────────────────

    def merge(self, new_orders: list[dict]) -> tuple[int, int]:
        """
        Sincroniza nuevas órdenes con la DB.
        Devuelve (nuevas, actualizadas).
        """
        before = self.count()
        self.upsert_orders(new_orders)
        after = self.count()
        new_count     = after - before
        updated_count = len(new_orders) - new_count
        return new_count, max(updated_count, 0)
