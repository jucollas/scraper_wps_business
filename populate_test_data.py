import sqlite3
import random
import string
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join("app", "orders.db")

PRODUCTS = [
    ("Café Grano 250 gr", 20000.00),
    ("Café Grano 500 gr", 35000.00),
    ("Café Molido 250 gr", 20000.00),
    ("Café Molido 500 gr", 35000.00),
    ("Chemex 400 ml silicona", 85000.00),
    ("Chemex de Vidrio y Bambú 400 ml", 95000.00),
    ("Cuchara Pinza 8gr", 20000.00),
    ("Drips de café 10 gr", 5000.00),
    ("Jarra Cuello de Cisne 600 ml", 80000.00),
    ("Jarra Latte + Lápiz", 69000.00),
    ("Miel de Abeja 250 ml", 25000.00),
    ("Miel de abeja 370 ml", 35000.00),
    ("Miel de Abeja 500 ml", 42000.00),
    ("Moka Italiana acero inoxidable", 65000.00),
    ("Molino eléctrico Café 125gr", 70000.00),
    ("Molino Manual Polietileno", 65000.00),
    ("Prensa Francesa 350 ml Negra", 35000.00),
    ("Prensa Francesa 600 ml Bambú", 69900.00),
    ("Termo insulado con filtro", 45000.00),
    ("Molino de café manual 50gr", 65000.00)
]

CLIENTES = [
    "Juan Pérez", "María Gómez", "Carlos Rodríguez", "Ana Fernández",
    "Luis Martínez", "Laura López", "Jorge Sánchez", "Elena Díaz",
    "Andrés Torres", "Sofía Ramírez", "Diego Flores", "Camila Ruiz",
    "Mateo Herrera", "Valentina Rojas", "Santiago Castro", "Isabella Medina",
    "Esteban Leyes", "Isabela Gutierrez", "Cafetería La Esquina", "Restaurante El Buen Sabor"
]

ESTADOS = ["Completado", "Pendiente", "Cancelado", "Enviado", "Envío en preparación", "Entregado"]
ESTADOS_WEIGHTS = [0.4, 0.15, 0.1, 0.15, 0.1, 0.1]  # Probabilidades de cada estado

def generate_random_id(length=11):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_random_date(start_year=2022, end_year=2026):
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)
    # Ensure end date is not in the future (optional, but good for realistic data)
    if end_date > datetime.now():
        end_date = datetime.now()
    
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

def populate_db(num_orders=1500):
    if not os.path.exists(DB_PATH):
        print(f"Error: La base de datos {DB_PATH} no existe. Ejecuta primero la aplicación para crearla.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Borrar datos existentes
    cursor.execute("DELETE FROM orders")
    print("Datos antiguos borrados.")

    # Generar y añadir nuevos datos
    count = 0
    for _ in range(num_orders):
        order_id = generate_random_id()
        wa_order_id = order_id  # En la app a veces son diferentes, pero podemos usar el mismo
        cliente = random.choice(CLIENTES)
        
        # Ocasionalmente un cliente compra múltiples cosas (sumamos precios y unimos nombres)
        num_items = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
        productos_comprados = random.choices(PRODUCTS, k=num_items)
        
        producto = " + ".join([p[0] for p in productos_comprados])
        monto = sum([p[1] for p in productos_comprados])
        
        # Fecha aleatoria entre 2022 y hoy
        fecha = get_random_date().strftime("%Y-%m-%d")
        
        estado = random.choices(ESTADOS, weights=ESTADOS_WEIGHTS)[0]
        synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO orders (id, whatsapp_order_id, cliente, producto, monto, fecha, estado, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, wa_order_id, cliente, producto, monto, fecha, estado, synced_at))
        
        count += 1

    conn.commit()
    conn.close()
    print(f"Base de datos poblada exitosamente con {count} órdenes de prueba.")

if __name__ == "__main__":
    # Generar unas 1500 órdenes para que las gráficas se vean bien llenas
    populate_db(1500)
