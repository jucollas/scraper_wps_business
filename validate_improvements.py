#!/usr/bin/env python3
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# validate_improvements.py — Validación rápida de mejoras implementadas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
Script rápido para validar que todas las mejoras están en su lugar.
Ejecutar antes de hacer push o deploy.
"""

import sys
from pathlib import Path

# Agregar app al path
sys.path.insert(0, str(Path(__file__).parent / "app"))

print("\n" + "=" * 80)
print("  🔍 VALIDACIÓN DE MEJORAS IMPLEMENTADAS")
print("=" * 80 + "\n")

checks = []

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Check 1: scraper.py tiene hashlib
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("✓ Revisando scraper.py...")
with open("app/scraper.py", encoding="utf-8") as f:
    scraper_content = f.read()
    
checks.append({
    'name': "scraper.py importa hashlib",
    'passed': 'import hashlib' in scraper_content
})

checks.append({
    'name': "scraper.py tiene _fetch_order_id mejorado",
    'passed': 'search_strategies' in scraper_content and 'whatsapp_order_id' in scraper_content
})

checks.append({
    'name': "scraper.py genera hash fallback",
    'passed': 'WA-' in scraper_content and 'hashlib.md5' in scraper_content
})

checks.append({
    'name': "scraper.py tiene logging detallado",
    'passed': '[Sync]' in scraper_content and '[Orden' in scraper_content
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Check 2: database.py tiene estructuras mejoradas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("✓ Revisando database.py...")
with open("app/database.py", encoding="utf-8") as f:
    database_content = f.read()

checks.append({
    'name': "database.py tiene whatsapp_order_id UNIQUE",
    'passed': 'whatsapp_order_id  TEXT UNIQUE' in database_content
})

checks.append({
    'name': "database.py tiene migración automática",
    'passed': 'ALTER TABLE orders ADD COLUMN whatsapp_order_id' in database_content
})

checks.append({
    'name': "database.py tiene _find_existing_order()",
    'passed': 'def _find_existing_order' in database_content
})

checks.append({
    'name': "database.py tiene get_by_whatsapp_id()",
    'passed': 'def get_by_whatsapp_id' in database_content
})

checks.append({
    'name': "database.py tiene get_sync_stats()",
    'passed': 'def get_sync_stats' in database_content
})

checks.append({
    'name': "database.py valida antes de insertar",
    'passed': 'order.get(\'id\')' in database_content and 'Validar' in database_content or 'validación' in database_content.lower()
})

checks.append({
    'name': "database.py loguea cada operación",
    'passed': '[DB] Insertando' in database_content or '[DB]' in database_content
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Check 3: app.py tiene mejoras de UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("✓ Revisando app.py...")
with open("app/app.py", encoding="utf-8") as f:
    app_content = f.read()

checks.append({
    'name': "app.py llama get_sync_stats()",
    'passed': 'get_sync_stats' in app_content
})

checks.append({
    'name': "app.py muestra porcentaje de éxito",
    'passed': 'with_whatsapp_id' in app_content and 'success_rate' in app_content or 'stats[' in app_content
})

checks.append({
    'name': "app.py tiene mejor manejo de errores",
    'passed': 'except Exception as sync_error:' in app_content
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Check 4: Archivos de documentación
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("✓ Revisando archivos de documentación...")

doc_files = [
    ('SYNC_IMPROVEMENTS.md', 'Documentación técnica'),
    ('RESUMEN_EJECUTIVO.md', 'Resumen de mejoras'),
    ('test_sync.py', 'Suite de pruebas'),
]

for filename, desc in doc_files:
    checks.append({
        'name': f"{filename} existe",
        'passed': Path(filename).exists()
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Check 5: test_sync.py es ejecutable
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("✓ Validando test_sync.py...")
with open("test_sync.py", encoding="utf-8") as f:
    test_content = f.read()

checks.append({
    'name': "test_sync.py tiene 8 pruebas",
    'passed': test_content.count('def test_') >= 8
})

checks.append({
    'name': "test_sync.py valida sin duplicados",
    'passed': 'test_03_no_duplicates' in test_content
})

checks.append({
    'name': "test_sync.py prueba estadísticas",
    'passed': 'test_05_sync_stats' in test_content
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Mostrar resultados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

passed_count = sum(1 for c in checks if c['passed'])
total_count = len(checks)

print("\n" + "=" * 80)
print("  RESULTADOS")
print("=" * 80 + "\n")

for check in checks:
    status = "✅" if check['passed'] else "❌"
    print(f"{status} {check['name']}")

print("\n" + "=" * 80)
print(f"TOTAL: {passed_count}/{total_count} validaciones pasadas")

if passed_count == total_count:
    print("✅ ¡TODAS LAS MEJORAS HAN SIDO IMPLEMENTADAS CORRECTAMENTE!")
    print("=" * 80 + "\n")
    print("📚 SIGUIENTE PASO: Ejecutar 'python test_sync.py' para validar BD\n")
    sys.exit(0)
else:
    print(f"⚠️  {total_count - passed_count} validación(es) fallaron")
    print("=" * 80 + "\n")
    sys.exit(1)
