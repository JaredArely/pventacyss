import pandas as pd
import database
import os

def importar():
    archivo_csv = 'INVENTARIOFEBRERO.csv'
    
    # 1. Verificar si el archivo existe en la carpeta
    if not os.path.exists(archivo_csv):
        print(f"❌ Error: El archivo '{archivo_csv}' no está en la carpeta del proyecto.")
        return

    # 2. Intentar conectar a la base de datos
    conn = database.get_db_connection()
    if conn is None:
        print("❌ ERROR DE CONEXIÓN: Verifica que el password en database.py y docker-compose.yml sean iguales.")
        return

    try:
        # 3. Leer CSV con limpieza automática (UTF-8 con BOM para Excel)
        df = pd.read_csv(archivo_csv, encoding='utf-8-sig', sep=None, engine='python')
        
        # Limpiar nombres de columnas (quitar espacios invisibles)
        df.columns = [c.strip() for c in df.columns]
        
        cur = conn.cursor()
        print(f"🚀 Iniciando importación... Columnas encontradas: {list(df.columns)}")
        
        count = 0
        for index, row in df.iterrows():
            # Extraer datos con nombres de columna exactos del Excel
            modelo = str(row.get('Modelo', '')).strip()
            # Si la fila está vacía o el modelo es 'nan', saltar
            if not modelo or modelo.lower() == 'nan':
                continue

            nombre = str(row.get('Descripcion', '')).strip()
            # Convertir cantidad a número, si falla ponemos 0
            try:
                stock = int(float(row.get('Cant', 0)))
            except:
                stock = 0
            
            categoria = str(row.get('Categoria', 'GENERAL')).strip()

            cur.execute("""
                INSERT INTO inventario_sucursal (modelo, nombre, stock, categoria, sucursal_id)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT (modelo) DO UPDATE SET 
                    stock = EXCLUDED.stock,
                    nombre = EXCLUDED.nombre;
            """, (modelo, nombre, stock, categoria))
            count += 1
        
        conn.commit()
        print(f"✅ ¡ÉXITO! Se cargaron {count} productos correctamente.")
        
    except Exception as e:
        print(f"❌ Error durante la carga: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    importar()