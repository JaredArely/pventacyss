import csv
import database
import os
import sys

def importar():
    # Ruta donde copiamos tu archivo
    csv_path = '/app/carga_inicial.csv'
    
    if not os.path.exists(csv_path):
        print("❌ ERROR: No encuentro el archivo 'carga_inicial.csv' dentro del contenedor.")
        return

    print("🔄 Conectando a la base de datos...")
    conn = database.get_db_connection()
    if not conn:
        print("❌ ERROR: No se pudo conectar a la BD.")
        return
        
    cur = conn.cursor()
    
    # Intentamos leer con diferentes codificaciones por si acaso
    rows = []
    encodings = ['utf-8-sig', 'latin-1', 'cp1252']
    
    for enc in encodings:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            print(f"✅ Archivo leído correctamente (Formato: {enc})")
            break
        except Exception:
            continue
            
    if not rows:
        print("❌ ERROR: No se pudo leer el archivo Excel. Verifica el formato.")
        return

    print(f"📦 Procesando {len(rows)} productos...")
    
    nuevos = 0
    actualizados = 0
    errores = 0
    
    for i, row in enumerate(rows):
        try:
            # Mapeo de columnas EXACTAS de tu archivo
            modelo = row.get('Modelo', '').strip()
            nombre = row.get('Descripcion', '').strip()
            categoria = row.get('Categoria', 'VARIOS').strip()
            
            # Limpieza de Stock (quitar comas o espacios)
            try:
                stock_raw = row.get('Cant', '0').replace(',', '').split('.')[0] # Toma solo entero
                stock = int(stock_raw)
            except:
                stock = 0

            if not modelo: # Saltamos filas vacías
                continue
            
            # 1. Verificamos si ya existe el producto
            cur.execute("SELECT id FROM inventario_sucursal WHERE modelo = %s", (modelo,))
            exists = cur.fetchone()
            
            if exists:
                # ACTUALIZAR (Si ya existe, actualizamos stock, nombre y categoría)
                cur.execute("""
                    UPDATE inventario_sucursal 
                    SET stock = %s, nombre = %s, categoria = %s
                    WHERE modelo = %s
                """, (stock, nombre, categoria, modelo))
                actualizados += 1
            else:
                # INSERTAR (Si es nuevo)
                # Precio = 0, Moneda = MXN, Proveedor = LOCAL por defecto
                cur.execute("""
                    INSERT INTO inventario_sucursal 
                    (modelo, nombre, stock, categoria, precio, moneda, proveedor, sucursal_id)
                    VALUES (%s, %s, %s, %s, 0, 'MXN', 'LOCAL', 1)
                """, (modelo, nombre, stock, categoria))
                nuevos += 1
                
        except Exception as e:
            print(f"⚠️ Error en fila {i+1} ({modelo}): {e}")
            errores += 1
            
    conn.commit()
    conn.close()
    
    print("\n" + "="*40)
    print("🚀 IMPORTACIÓN FINALIZADA")
    print(f"✨ Productos Nuevos Creados: {nuevos}")
    print(f"🔄 Productos Actualizados:   {actualizados}")
    print(f"⚠️ Errores:                  {errores}")
    print("="*40)

if __name__ == '__main__':
    importar()