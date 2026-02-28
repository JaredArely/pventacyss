import psycopg2
import csv
import os
import datetime

# CONFIGURACIÓN (Asegúrate que coincida con tu app.py)
DB_HOST = "localhost"
DB_NAME = "pos_sistema"
DB_USER = "postgres"
DB_PASS = "Cyss2017"

def conectar():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port="5432")

def migrar_datos():
    print("--- INICIANDO IMPORTACIÓN DE ÓRDENES ---")
    conn = conectar()
    cur = conn.cursor()
    
    # 1. Asegurar tabla (Por si no reiniciaste app.py aún)
    cur.execute("""CREATE TABLE IF NOT EXISTS ordenes_trabajo (
        id SERIAL PRIMARY KEY,
        folio VARCHAR(50) UNIQUE,
        cliente TEXT,
        estatus VARCHAR(50),
        pagado TEXT,
        metodo_pago VARCHAR(50),
        fecha DATE,
        fecha_registro TIMESTAMP DEFAULT NOW()
    );""")
    
    archivo = 'ORDENES DE TRABAJO.xlsx - Hoja1.csv'
    if not os.path.exists(archivo):
        print(f"❌ ERROR: No encuentro el archivo {archivo}")
        return

    contador = 0
    with open(archivo, encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) # Saltar línea vacía inicial si existe
        next(reader) # Saltar encabezados
        
        for row in reader:
            if not row or len(row) < 6: continue
            
            # Mapeo según tu archivo CSV
            folio = row[1].strip()
            cliente = row[2].strip().upper()
            estatus = row[3].strip().upper()
            pagado = row[4].strip().upper()
            metodo = row[5].strip().upper()
            fecha_str = row[6].strip()
            
            # Convertir fecha
            fecha_final = None
            if fecha_str:
                try:
                    fecha_final = fecha_str # PostgreSQL suele aceptar YYYY-MM-DD directo
                except: pass

            if folio:
                try:
                    cur.execute("""
                        INSERT INTO ordenes_trabajo (folio, cliente, estatus, pagado, metodo_pago, fecha)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (folio) DO UPDATE SET 
                            cliente=EXCLUDED.cliente, 
                            estatus=EXCLUDED.estatus,
                            pagado=EXCLUDED.pagado;
                    """, (folio, cliente, estatus, pagado, metodo, fecha_final))
                    contador += 1
                except Exception as e:
                    print(f"Error en folio {folio}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ IMPORTACIÓN COMPLETADA: {contador} órdenes cargadas exitosamente.")

if __name__ == "__main__":
    migrar_datos()