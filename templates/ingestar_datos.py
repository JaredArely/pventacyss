import psycopg2
import csv
import os

# CONFIGURACIÓN DE CONEXIÓN
DB_HOST = "localhost"  # Si corres esto DESDE TU PC (fuera del docker)
# DB_HOST = "db"       # Si corres esto DENTRO del contenedor
DB_NAME = "pos_sistema"
DB_USER = "postgres"
DB_PASS = "Cyss2017"

def conectar():
    try:
        return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port="5432")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def ejecutar_ingesta():
    print("--- 🟢 INICIANDO INGESTA DE DATOS HISTÓRICOS ---")
    conn = conectar()
    if not conn: return

    cur = conn.cursor()
    archivo = 'ORDENES.xlsx'

    if not os.path.exists(archivo):
        print(f"❌ No encuentro el archivo: {archivo}")
        return

    registros = 0
    with open(archivo, encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Saltamos las líneas de encabezado que detecté en tu archivo
        next(reader, None) # Línea vacía
        next(reader, None) # Encabezados (ORDEN, CLIENTE...)

        for row in reader:
            if not row or len(row) < 6: continue
            
            try:
                # Mapeo exacto de tus columnas
                folio = row[1].strip()
                if not folio: continue

                cliente = row[2].strip().upper()
                estatus = row[3].strip().upper()
                pagado = row[4].strip().upper()
                metodo = row[5].strip().upper()
                fecha = row[6].strip()

                # Validación simple de fecha
                if len(fecha) < 5: fecha = None

                # Insertar o Actualizar
                query = """
                    INSERT INTO ordenes_trabajo 
                    (folio, cliente, estatus, pagado, metodo_pago, fecha)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (folio) DO UPDATE SET
                        cliente=EXCLUDED.cliente,
                        estatus=EXCLUDED.estatus,
                        pagado=EXCLUDED.pagado,
                        metodo_pago=EXCLUDED.metodo_pago,
                        fecha=EXCLUDED.fecha;
                """
                cur.execute(query, (folio, cliente, estatus, pagado, metodo, fecha))
                registros += 1
                print(f"   Processed: Folio {folio} - {cliente}")

            except Exception as e:
                print(f"⚠️ Error en fila: {row} -> {e}")

    conn.commit()
    conn.close()
    print(f"--- ✅ PROCESO TERMINADO: {registros} órdenes importadas ---")

if __name__ == "__main__":
    ejecutar_ingesta()