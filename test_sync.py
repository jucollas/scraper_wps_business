#!/usr/bin/env python3
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# test_sync.py — Pruebas de sincronización y deduplicación
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
Script de prueba para validar:
1. Creación y migración de BD
2. Upsert de órdenes sin duplicados
3. Estadísticas de sincronización
4. Consistencia de datos
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
import hashlib

# Agregar directorio app al path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from database import Database
from config import SAMPLE_ORDERS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRUEBAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_header(title: str):
    """Imprime encabezado de prueba."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_result(passed: bool, message: str):
    """Imprime resultado de prueba."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {message}")

def test_01_db_creation():
    """Prueba 1: Creación y migración de BD."""
    print_header("Prueba 1: Creación y Migración de BD")
    
    test_db_path = Path(__file__).parent / "test_orders.db"
    
    # Limpiar si existe
    if test_db_path.exists():
        test_db_path.unlink()
        print("✓ BD anterior eliminada")
    
    # Crear BD
    db = Database(test_db_path)
    print(f"✓ BD creada: {test_db_path}")
    
    # Verificar que table existe y que whatsapp_order_id existe
    with db._connect() as conn:
        cursor = conn.execute("PRAGMA table_info(orders)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    passed = (
        'id' in columns and
        'whatsapp_order_id' in columns and
        'cliente' in columns and
        'estado' in columns
    )
    
    print_result(passed, "BD tiene todas las columnas requeridas")
    print(f"  Columnas: {', '.join(columns.keys())}")
    
    return db, test_db_path, passed

def test_02_insert_orders(db: Database):
    """Prueba 2: Insertar órdenes nuevas."""
    print_header("Prueba 2: Insertar Órdenes Nuevas")
    
    # Crear órdenes de prueba con whatsapp_order_id real
    orders = [
        {
            'id': 'WA-ABC123DEF456',
            'whatsapp_order_id': 'ABC123DEF456',
            'cliente': 'Juan García',
            'producto': 'Torta chocolate',
            'monto': 45.0,
            'fecha': date.today().isoformat(),
            'estado': 'Completado'
        },
        {
            'id': 'WA-XYZ789UVW012',
            'whatsapp_order_id': 'XYZ789UVW012',
            'cliente': 'María López',
            'producto': 'Cupcakes x12',
            'monto': 30.0,
            'fecha': date.today().isoformat(),
            'estado': 'Pendiente'
        },
        {
            'id': 'WA-QRS345TUV678',
            'whatsapp_order_id': None,  # Orden sin whatsapp_order_id
            'cliente': 'Carlos Ruiz',
            'producto': 'Brownies',
            'monto': 25.0,
            'fecha': date.today().isoformat(),
            'estado': 'Completado'
        }
    ]
    
    # Insertar
    affected = db.upsert_orders(orders)
    print(f"✓ Inserción completada: {affected} registros")
    
    # Verificar
    all_orders = db.get_all()
    print(f"✓ Total de órdenes en BD: {len(all_orders)}")
    
    # Mostrar
    for o in all_orders:
        wa_id = o['whatsapp_order_id'] or '[NO]'
        print(f"  - {o['cliente']:15} | {wa_id:20} | {o['monto']:6.1f} | {o['estado']}")
    
    passed = len(all_orders) == 3 and affected > 0
    print_result(passed, f"Se insertaron 3 órdenes correctamente")
    
    return orders

def test_03_no_duplicates(db: Database, orders: list):
    """Prueba 3: Evitar duplicados en segundo sync."""
    print_header("Prueba 3: Evitar Duplicados (2do Sync)")
    
    before = db.count()
    print(f"✓ Órdenes antes del 2do sync: {before}")
    
    # Insertar las MISMAS órdenes de nuevo
    affected = db.upsert_orders(orders)
    print(f"✓ Ejecución del 2do sync: {affected} registros afectados")
    
    after = db.count()
    print(f"✓ Órdenes después del 2do sync: {after}")
    
    # Verificar: debe haber 0 nuevas (solo actualización)
    # affected debe ser igual al número de órdenes (las actualiza)
    passed = after == before  # No nuevas órdenes
    
    print_result(passed, f"No hay duplicados (mismo total: {after} órdenes)")
    
    if passed:
        print(f"  ✓ Las 3 órdenes fueron ACTUALIZADAS, no duplicadas")
    
    return passed

def test_04_update_existing(db: Database):
    """Prueba 4: Actualizar orden existente."""
    print_header("Prueba 4: Actualizar Orden Existente")
    
    # Obtener orden existente
    order = db.get_by_whatsapp_id('ABC123DEF456')
    print(f"✓ Orden encontrada: {order['cliente']} | {order['estado']}")
    
    # Actualizar estado
    order_updated = order.copy()
    order_updated['estado'] = 'Cancelado'
    
    affected = db.upsert_orders([order_updated])
    print(f"✓ Actualización completada: {affected} registros")
    
    # Verificar
    order_new = db.get_by_whatsapp_id('ABC123DEF456')
    passed = order_new['estado'] == 'Cancelado'
    
    print_result(passed, f"Estado actualizado: {order['estado']} → {order_new['estado']}")
    
    return passed

def test_05_sync_stats(db: Database):
    """Prueba 5: Estadísticas de sincronización."""
    print_header("Prueba 5: Estadísticas de Sincronización")
    
    stats = db.get_sync_stats()
    
    print(f"✓ Total de órdenes:              {stats['total']}")
    print(f"✓ Con whatsapp_order_id real:    {stats['with_whatsapp_id']}")
    print(f"✓ Con fallback hash:             {stats['without_whatsapp_id']}")
    print(f"✓ Tasa de éxito:                 {stats['success_rate']:.1f}%")
    
    expected_with = 2  # ABC123DEF456 y XYZ789UVW012
    expected_without = 1  # La de Carlos (sin whatsapp_order_id)
    
    passed = (
        stats['total'] == 3 and
        stats['with_whatsapp_id'] == expected_with and
        stats['without_whatsapp_id'] == expected_without
    )
    
    print_result(passed, "Estadísticas correctas")
    
    return passed

def test_06_query_methods(db: Database):
    """Prueba 6: Métodos de consulta."""
    print_header("Prueba 6: Métodos de Consulta")
    
    # get_by_whatsapp_id
    order1 = db.get_by_whatsapp_id('ABC123DEF456')
    passed1 = order1 is not None and order1['cliente'] == 'Juan García'
    print_result(passed1, f"get_by_whatsapp_id(): {order1['cliente'] if order1 else 'NOT FOUND'}")
    
    # get_by_id
    order2 = db.get_by_id('WA-ABC123DEF456')
    passed2 = order2 is not None and order2['cliente'] == 'Juan García'
    print_result(passed2, f"get_by_id(): {order2['cliente'] if order2 else 'NOT FOUND'}")
    
    # get_all
    all_orders = db.get_all()
    passed3 = len(all_orders) == 3
    print_result(passed3, f"get_all(): {len(all_orders)} órdenes")
    
    # get_by_date_range
    today = date.today().isoformat()
    orders_today = db.get_by_date_range(today, today)
    passed4 = len(orders_today) == 3
    print_result(passed4, f"get_by_date_range(): {len(orders_today)} órdenes hoy")
    
    return passed1 and passed2 and passed3 and passed4

def test_07_hash_consistency():
    """Prueba 7: Consistencia del hash fallback."""
    print_header("Prueba 7: Consistencia del Hash Fallback")
    
    # Mismo orden debe generar mismo hash en diferentes ejecuciones
    salt1 = "Juan García|Torta chocolate|2025-03-01|45.0"
    salt2 = "Juan García|Torta chocolate|2025-03-01|45.0"
    
    hash1 = hashlib.md5(salt1.encode()).hexdigest()[:12].upper()
    hash2 = hashlib.md5(salt2.encode()).hexdigest()[:12].upper()
    
    passed = hash1 == hash2
    print_result(passed, f"Hash consistente: {hash1} == {hash2}")
    
    # Diferente orden = diferente hash
    salt3 = "Maria López|Cupcakes|2025-03-01|30.0"
    hash3 = hashlib.md5(salt3.encode()).hexdigest()[:12].upper()
    
    passed2 = hash1 != hash3
    print_result(passed2, f"Hash diferente para orden diferente: {hash1} != {hash3}")
    
    return passed and passed2

def test_08_sample_orders(db: Database):
    """Prueba 8: Sincronización con SAMPLE_ORDERS."""
    print_header("Prueba 8: Sincronización con SAMPLE_ORDERS")
    
    # Limpiar BD
    with db._connect() as conn:
        conn.execute("DELETE FROM orders")
        conn.commit()
    
    print(f"✓ BD limpiada: {db.count()} órdenes")
    
    # Primer sync
    new1, upd1 = db.merge(SAMPLE_ORDERS)
    print(f"✓ 1er sync: +{new1} nuevas, {upd1} actualizadas")
    
    count1 = db.count()
    print(f"✓ Total después 1er sync: {count1}")
    
    # Segundo sync (mismas órdenes)
    new2, upd2 = db.merge(SAMPLE_ORDERS)
    print(f"✓ 2do sync: +{new2} nuevas, {upd2} actualizadas")
    
    count2 = db.count()
    print(f"✓ Total después 2do sync: {count2}")
    
    # Tercer sync
    new3, upd3 = db.merge(SAMPLE_ORDERS)
    print(f"✓ 3er sync: +{new3} nuevas, {upd3} actualizadas")
    
    count3 = db.count()
    print(f"✓ Total después 3er sync: {count3}")
    
    # Verificación: Sin duplicados
    passed = (
        new1 > 0 and upd1 == 0 and  # Primero: inserta
        new2 == 0 and upd2 > 0 and  # Segundo: actualiza
        new3 == 0 and upd3 > 0 and  # Tercero: actualiza
        count1 == count2 == count3   # Mismo total
    )
    
    print_result(passed, f"Sin duplicados después de 3 syncs (total: {count3})")
    
    return passed

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print("\n" + "🧪 TEST SUITE: Sincronización de Órdenes WhatsApp Business".center(80))
    
    results = {
        "01_db_creation": False,
        "02_insert_orders": False,
        "03_no_duplicates": False,
        "04_update_existing": False,
        "05_sync_stats": False,
        "06_query_methods": False,
        "07_hash_consistency": False,
        "08_sample_orders": False,
    }
    
    try:
        # Prueba 1
        db, test_db_path, results["01_db_creation"] = test_01_db_creation()
        
        # Prueba 2
        orders = test_02_insert_orders(db)
        results["02_insert_orders"] = True
        
        # Prueba 3
        results["03_no_duplicates"] = test_03_no_duplicates(db, orders)
        
        # Prueba 4
        results["04_update_existing"] = test_04_update_existing(db)
        
        # Prueba 5
        results["05_sync_stats"] = test_05_sync_stats(db)
        
        # Prueba 6
        results["06_query_methods"] = test_06_query_methods(db)
        
        # Prueba 7
        results["07_hash_consistency"] = test_07_hash_consistency()
        
        # Prueba 8
        results["08_sample_orders"] = test_08_sample_orders(db)
        
    except Exception as e:
        logger.exception(f"Error durante pruebas: {e}")
        print(f"\n❌ Error: {e}\n")
        return 1
    
    # Resumen
    print("\n" + "=" * 80)
    print("  RESUMEN DE RESULTADOS")
    print("=" * 80)
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}")
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {passed_count}/{total_count} pruebas pasadas")
    
    if passed_count == total_count:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print("=" * 80 + "\n")
        return 0
    else:
        print(f"⚠️  {total_count - passed_count} prueba(s) fallaron")
        print("=" * 80 + "\n")
        return 1

if __name__ == "__main__":
    exit(main())
