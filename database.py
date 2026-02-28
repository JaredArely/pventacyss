import psycopg2
from psycopg2.extras import RealDictCursor
import math
import os

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host='cyss_db', 
            database='postgres',
            user='postgres',
            password='password', # Debe coincidir con docker-compose
            port='5432'
        )
        return conn
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def redondear_cyss(valor):
    if valor is None: return 0.0
    try: return round(float(valor), 2)
    except: return 0.0

def reparar_base_datos_segura():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            conn.autocommit = True
            
            print("🔄 Iniciando reparación de base de datos...")

            # 1. Sucursales
            cur.execute("CREATE TABLE IF NOT EXISTS sucursales (id SERIAL PRIMARY KEY, nombre_comercial VARCHAR(100) UNIQUE NOT NULL);")
            cur.execute("INSERT INTO sucursales (id, nombre_comercial) VALUES (1, 'ARAUCARIAS'), (2, 'AMERICAS') ON CONFLICT (id) DO NOTHING;")
            
            # 2. Usuarios
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY, 
                    nombre_usuario VARCHAR(50) UNIQUE NOT NULL, 
                    rol VARCHAR(20) DEFAULT 'vendedor', 
                    sucursal_id INT REFERENCES sucursales(id)
                );
            """)
            
            # Columna Password
            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password VARCHAR(100);")
            
            # 3. Usuarios (Karina, Jared y Mario)
            # Karina - Operador (Almacén, Calculadora, Garantías, POS, Salidas, Órdenes)
            cur.execute("INSERT INTO usuarios (nombre_usuario, rol, sucursal_id, password) VALUES ('Karina', 'operador', 1, 'Cyss2017') ON CONFLICT (nombre_usuario) DO NOTHING;")
            cur.execute("UPDATE usuarios SET password = 'Cyss2017', rol = 'operador' WHERE nombre_usuario = 'Karina';")
            
            # Jared - Admin
            cur.execute("INSERT INTO usuarios (nombre_usuario, rol, sucursal_id, password) VALUES ('Jared', 'admin', 1, 'Cyss2017') ON CONFLICT (nombre_usuario) DO NOTHING;")
            cur.execute("UPDATE usuarios SET password = 'Cyss2017', rol = 'admin' WHERE nombre_usuario = 'Jared';")
            
            # Mario - Limitado (Recordando que solo ve Almacén, Calculadora y Cotizador)
            cur.execute("INSERT INTO usuarios (nombre_usuario, rol, sucursal_id, password) VALUES ('Mario', 'limitado', 2, 'Cyss2017') ON CONFLICT (nombre_usuario) DO NOTHING;")
            cur.execute("UPDATE usuarios SET password = 'Cyss2017', rol = 'limitado' WHERE nombre_usuario = 'Mario';")
            
            # 4. Inventario
            cur.execute("CREATE TABLE IF NOT EXISTS inventario_sucursal (id SERIAL PRIMARY KEY, modelo VARCHAR(100) UNIQUE, nombre TEXT, stock INTEGER DEFAULT 0, precio NUMERIC DEFAULT 0, categoria VARCHAR(50), sucursal_id INT REFERENCES sucursales(id));")
            cur.execute("ALTER TABLE inventario_sucursal ADD COLUMN IF NOT EXISTS moneda VARCHAR(10) DEFAULT 'MXN';")
            cur.execute("ALTER TABLE inventario_sucursal ADD COLUMN IF NOT EXISTS stock_americas INTEGER DEFAULT 0;")
            cur.execute("ALTER TABLE inventario_sucursal ADD COLUMN IF NOT EXISTS proveedor VARCHAR(50) DEFAULT 'LOCAL';")
            
            # 5. Movimientos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS movimientos_inventario (
                    id SERIAL PRIMARY KEY,
                    producto_id INT,
                    cantidad INT,
                    tipo VARCHAR(50),
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_id INT
                );
            """)
            cur.execute("ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS sucursal_id INT REFERENCES sucursales(id);")

            # 6. Módulo de Garantías (Ahora está dentro del flujo correcto)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS garantias (
                    id SERIAL PRIMARY KEY,
                    folio VARCHAR(20) UNIQUE,
                    tipo_servicio VARCHAR(50), -- 'PROVEEDOR' o 'MANTENIMIENTO'
                    cliente VARCHAR(100),
                    modelo VARCHAR(100),
                    serie VARCHAR(100),
                    accesorios TEXT,
                    falla TEXT,
                    estado VARCHAR(50) DEFAULT 'Recibido',
                    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sucursal_id INT REFERENCES sucursales(id)
                );
            """)
            
            conn.close()
            print("✅ Base de datos CORREGIDA exitosamente.")

        except Exception as e:
            print(f"❌ Error durante la reparación: {e}")
    else:
        print("⚠️ No se pudo conectar a la base de datos.")

if __name__ == "__main__":
    reparar_base_datos_segura()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS garantias (
        id SERIAL PRIMARY KEY,
        folio VARCHAR(20) UNIQUE,
        tipo_servicio VARCHAR(50), -- 'PROVEEDOR' o 'MANTENIMIENTO'
        cliente VARCHAR(100),
        modelo VARCHAR(100),
        serie VARCHAR(100),
        accesorios TEXT,
        falla TEXT,
        estado VARCHAR(50) DEFAULT 'Recibido',
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sucursal_id INT REFERENCES sucursales(id)
    );
""")