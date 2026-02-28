from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from fpdf import FPDF
import os
import math
import datetime
import json
from psycopg2.extras import RealDictCursor
import database
import config
import syscom_logic

try:
    import database
    import config
    import syscom_logic
    db_available = True
except ImportError:
    print("⚠️ Módulos de BD no encontrados. Ejecutando en modo 'Solo Cotizador'.")
    db_available = False
    # Configuración de respaldo por si fallan los imports
    config = type('obj', (object,), {
        'TIPO_CAMBIO_DOLAR': 18.0, 
        'MARGEN_PUBLICO': 0.75, 
        'MARGEN_PREFERENTE': 0.80, 
        'MARGEN_INTEGRADOR': 0.90
    })
bp = Blueprint('main', __name__)

# ==========================================
# 1. RUTAS DE ACCESO Y MENÚ
# ==========================================
@bp.route('/')
def menu():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    return render_template('menu.html', user=session['username'], sucursal=session.get('sucursal_nombre', 'Cyss'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 1. Acceso de emergencia (Solo si la BD falla)
        if username == 'admin' and password == 'Cyss2017':
            session.update({'user_id': 0, 'username': 'Administrador', 'rol': 'admin', 'sucursal_id': 1})
            return redirect(url_for('main.menu'))

        # 2. Acceso por Base de Datos (Jared y Mario)
        conn = database.get_db_connection()
        if conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # Buscamos por nombre_usuario (como está en tu database.py)
            cur.execute("SELECT * FROM usuarios WHERE nombre_usuario = %s", (username,))
            user = cur.fetchone()
            conn.close()

            if user and user['password'] == password:
                session.update({
                    'user_id': user['id'],
                    'username': user['nombre_usuario'],
                    'rol': user['rol'],
                    'sucursal_id': user['sucursal_id']
                })
                return redirect(url_for('main.menu'))
        
        return render_template('login.html', error="Usuario o contraseña incorrectos")
    
    return render_template('login.html')

# ==========================================
# 2. EL NUEVO COTIZADOR (ESTILO EXCEL)
# ==========================================
@bp.route('/nuevo_cotizador')
def nuevo_cotizador():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    now = datetime.datetime.now()
    fecha_hoy = now.strftime("%d/%m/%Y")
    folio_sugerido = f"COT-{int(now.timestamp())}"
    dolar = getattr(config, 'TIPO_CAMBIO_DOLAR', 18.0)
    return render_template('nuevo_cotizador.html', 
                           fecha=fecha_hoy, 
                           folio=folio_sugerido,
                           vendedor=session.get('username').upper(),
                           dolar_default=config.TIPO_CAMBIO_DOLAR)

# ==========================================
# 3. GENERADOR PDF (NUEVO - CLON EXCEL)
# ==========================================
class PDF_Excel(FPDF):
    def __init__(self):
        # Iniciamos FPDF
        FPDF.__init__(self, orientation='P', unit='mm', format='Letter')
        # ARREGLO FINAL: Definimos la fuente AQUÍ MISMO para que nunca falte
        self.set_font('Arial', '', 9)

    def header(self):
        pass
    def footer(self):
        pass

@bp.route('/api/generar_pdf_cotizacion', methods=['POST'])
def generar_pdf_cotizacion():
    try:
        if not os.path.exists('static'):
            os.makedirs('static')
            
        data = request.json
        cliente = data.get('cliente', 'CLIENTE MOSTRADOR').upper()
        vendedor = data.get('vendedor', 'OFICINA CYSS').upper()
        items = data.get('items', [])
        total_float = float(data.get('total_final', 0))
        tipo_iva = data.get('tipo_iva', 'incluido') # 'incluido' o 'desglosado'
        
        # Desglose Final (Pie de página) - Siempre igual matemáticamente
        subtotal_final_float = total_float / 1.16
        iva_final_float = total_float - subtotal_final_float

        subtotal_fmt = f"$ {subtotal_final_float:,.2f}"
        iva_fmt = f"$ {iva_final_float:,.2f}"
        total_fmt = f"$ {total_float:,.2f}"

        # Fecha
        meses = {1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
                 7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"}
        now = datetime.datetime.now()
        fecha_str = f"XALAPA, VER A {now.day} DE {meses[now.month]} DEL {now.year}"

        def limpiar(txt):
            if not txt: return ""
            rep = {'•': '-', '®': '', '©': '', 'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ñ': 'N'}
            t = str(txt)
            for k, v in rep.items(): t = t.replace(k, v)
            try: return t.encode('latin-1', 'replace').decode('latin-1')
            except: return t

        # INICIAR PDF
        pdf = PDF_Excel()
        pdf.set_font('Arial', '', 9)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_font('Arial', '', 9)

        # LOGOS
        logo_cyss = os.path.join('static', 'logocyss.png')
        if not os.path.exists(logo_cyss): logo_cyss = os.path.join('static', 'logocyss.jpg')
        logo_hik = os.path.join('static', 'logohik.png')
        if not os.path.exists(logo_hik): logo_hik = os.path.join('static', 'logohik.jpg')

        if os.path.exists(logo_cyss): pdf.image(logo_cyss, 10, 8, 35)
        if os.path.exists(logo_hik): pdf.image(logo_hik, 160, 8, 40)
        if not os.path.exists(logo_cyss) and not os.path.exists(logo_hik): pdf.ln(20)

        # --- CORRECCIÓN DE "ENCIMADO" ---
        # Bajamos el cursor hasta 50mm para librar los logos (que miden ~35-40mm)
        pdf.set_y(50)

        # ENCABEZADO
        # Fecha a la derecha
        pdf.cell(0, 5, fecha_str, 0, 1, 'R')
        pdf.ln(5)
        
        # Cliente a la izquierda
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, limpiar(cliente), 0, 1, 'L')
        
        # Texto de saludo
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, limpiar('Reciba de Computadoras y Sistemas del Sureste un cordial saludo y por medio de la presente le hacemos de su conocimiento la siguiente cotizacion:'))
        pdf.ln(5)

        # TABLA
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(240, 240, 240)
        pdf.set_draw_color(200, 200, 200)
        
        w = [12, 108, 20, 25, 25] 
        h = 6
        
        # Títulos dinámicos
        if tipo_iva == 'desglosado':
            titulo_pu = 'P. UNIT (S/IVA)'
            titulo_sub = 'SUBTOTAL'
        else:
            titulo_pu = 'P. UNIT (C/IVA)'
            titulo_sub = 'TOTAL'

        pdf.cell(w[0], h, 'CANT.', 1, 0, 'C', 1)
        pdf.cell(w[1], h, 'CONCEPTO', 1, 0, 'C', 1)
        pdf.cell(w[2], h, 'UNIDAD', 1, 0, 'C', 1)
        pdf.cell(w[3], h, titulo_pu, 1, 0, 'C', 1)
        pdf.cell(w[4], h, titulo_sub, 1, 1, 'C', 1)
        
        pdf.set_font('Arial', '', 8)
        
        for item in items:
            concepto_full = f"{item.get('modelo','')} {item.get('descripcion','')}".strip()
            
            # El precio unitario viene del frontend (ya redondeado y con IVA si aplica)
            precio_base = float(item['precio_unitario'])
            importe_base = float(item['importe'])

            # Lógica de Visualización
            if tipo_iva == 'desglosado':
                # Quitamos el IVA para mostrar NETO en la tabla
                pu_imprimir = precio_base / 1.16
                imp_imprimir = importe_base / 1.16
            else:
                # Mostramos precio LLENO (con IVA)
                pu_imprimir = precio_base
                imp_imprimir = importe_base

            pu_txt = f"$ {pu_imprimir:,.2f}"
            imp_txt = f"$ {imp_imprimir:,.2f}"

            x = pdf.get_x()
            y = pdf.get_y()
            
            pdf.set_xy(x + w[0], y)
            pdf.multi_cell(w[1], 5, limpiar(concepto_full), 1, 'L')
            h_actual = pdf.get_y() - y
            
            pdf.set_xy(x, y)
            pdf.cell(w[0], h_actual, str(item['cantidad']), 1, 0, 'C')
            pdf.set_xy(x + w[0] + w[1], y)
            pdf.cell(w[2], h_actual, 'Pza', 1, 0, 'C')
            pdf.cell(w[3], h_actual, pu_txt, 1, 0, 'R')
            pdf.cell(w[4], h_actual, imp_txt, 1, 0, 'R')
            pdf.ln(h_actual)

        # --- TOTALES (LÓGICA NUEVA) ---
        pdf.ln(5)
        
        if tipo_iva == 'desglosado':
            # MODO DESGLOSADO: Mostramos Subtotal, IVA y Total
            pdf.set_font('Arial', 'B', 9)
            pdf.set_x(-65) 
            pdf.cell(25, 6, 'Subtotal', 0, 0, 'R')
            pdf.cell(30, 6, subtotal_fmt, 1, 1, 'R')
            
            pdf.set_x(-65) 
            pdf.cell(25, 6, 'IVA (16%)', 0, 0, 'R')
            pdf.cell(30, 6, iva_fmt, 1, 1, 'R')

            pdf.set_x(-65) 
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(25, 8, 'Total', 0, 0, 'R')
            pdf.cell(30, 8, total_fmt, 1, 1, 'R')
        
        else:
            # MODO IVA INCLUIDO: Solo mostramos el TOTAL FINAL
            pdf.set_x(-65) 
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(25, 8, 'Total', 0, 0, 'R')
            pdf.cell(30, 8, total_fmt, 1, 1, 'R')

        # BANCO
        y_final = pdf.get_y()
        pdf.set_xy(10, y_final + 5)
        
        pdf.set_fill_color(255, 255, 0)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(100, 5, limpiar('Pagos a Cuenta Bancomer'), 0, 1, 'L', 1)
        pdf.set_font('Arial', '', 8)
        pdf.set_x(10)
        pdf.cell(100, 4, limpiar('Cta. 0464467019 a Nombre de: Jorge Arnoldo Choel Robles'), 0, 1, 'L')
        pdf.set_x(10)
        pdf.cell(100, 4, limpiar('Clabe Interbancaria: 0128 4000 4644 6701 92'), 0, 1, 'L')
        # PIE
        pdf.ln(10)
        condiciones = [
            "Forma de pago: 50% anticipo y el 50% a la entrega",
            "Nuestros productos cuentan con 1 año de garantia",
            "Esta cotizacion tiene una vigencia de 2 dias naturales",
            "Precios incluyen el 16% de IVA",
            "Enviar comprobante a facturacion@cyssxalapa.com.mx"
        ]
        for c in condiciones: pdf.cell(0, 4, "- " + limpiar(c), 0, 1, 'L')

        pdf.ln(10)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, 'ATTE.', 0, 1, 'C')
        pdf.cell(0, 5, limpiar(vendedor), 0, 1, 'C')

        nombre = f"Cot_{cliente.split()[0]}_{now.strftime('%d%m%y')}.pdf"
        ruta = os.path.join('static', nombre)
        pdf.output(ruta)
        
        return jsonify({'status': 'success', 'url': f'/static/{nombre}'})

    except Exception as e:
        print(f"ERROR PDF: {e}") # Ver error en consola Docker
        return jsonify({'status': 'error', 'message': str(e)})
# ==========================================
# 4. LABORATORIO SYSCOM
# ==========================================
@bp.route('/laboratorio_syscom')
def laboratorio_syscom():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    return render_template('index.html', vendedor_nombre=session.get('username'), sucursal_id=session.get('sucursal_id'))
@bp.route('/buscar_productos')
def buscar_productos():
    q = request.args.get('q', '').strip().upper()
    dolar_url = request.args.get('dolar', 0)
    if not q: return jsonify([])
    resultados_finales = []
    if db_available:
        try:
            conn = database.get_db_connection()
            if conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT modelo, nombre, precio, proveedor, stock, stock_americas, COALESCE(moneda, 'MXN') as moneda FROM inventario_sucursal WHERE modelo ILIKE %s OR nombre ILIKE %s", (f'%{q}%', f'%{q}%'))
                for loc in cur.fetchall():
                     resultados_finales.append({
                        "modelo": loc['modelo'],
                        "nombre": f"[{loc['proveedor']}] {loc['nombre']}",
                        "precio_venta": float(loc['precio'] or 0),
                        "stock_label": f"Local: {loc['stock']}",
                        "origen": "LOCAL",
                        "moneda": loc['moneda']
                    })
                conn.close()
        except: pass
    if db_available:
        try:
            sys_res = syscom_logic.buscar_syscom_api(q, dolar_url)
            for p in sys_res:
                if not any(r['modelo'] == p['modelo'] for r in resultados_finales):
                    resultados_finales.append(p)
        except: pass
    return jsonify(resultados_finales)
# ==========================================
# 5. OTRAS PÁGINAS (VENTAS, INVENTARIO)
# ==========================================
@bp.route('/inventario')
def inventario():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    return render_template('inventario.html', rol=session.get('rol'), suc_id=session.get('sucursal_id'))

@bp.route('/calculadora')
def calculadora_rapida():
    return render_template('calculadora.html', dolar_default=config.TIPO_CAMBIO_DOLAR, m_publico=config.MARGEN_PUBLICO, m_preferente=config.MARGEN_PREFERENTE, m_integrador=config.MARGEN_INTEGRADOR)

@bp.route('/ventas')
def ventas(): return render_template('ventas.html')

@bp.route('/ordenes') 
def ordenes_page(): return render_template('ordenes.html')

@bp.route('/material_tecnico')
def material_tecnico(): return render_template('material_tecnico.html')

@bp.route('/notas')
def notas(): return render_template('notas.html')

@bp.route('/agregar_material')
def agregar_material_page(): return render_template('agregar_material.html')

# ==========================================
# 6. APIs (BUSCADOR, INVENTARIO, ETC)
# ==========================================
@bp.route('/api/inventario/obtener')
def api_obtener_inventario():
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat', 'TODAS')
    
    conn = database.get_db_connection()
    if not conn: return jsonify([])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = """
            SELECT id, modelo, nombre, 
                   COALESCE(stock, 0) as stock_arau, 
                   COALESCE(stock_americas, 0) as stock_ame, 
                   precio, 
                   COALESCE(moneda, 'MXN') as moneda, 
                   COALESCE(categoria, 'GENERAL') as categoria 
            FROM inventario_sucursal 
            WHERE 1=1
        """
        params = []
        if q:
            query += " AND (modelo ILIKE %s OR nombre ILIKE %s)"
            params.extend([f'%{q}%', f'%{q}%'])
        if cat != 'TODAS':
            query += " AND categoria = %s"
            params.append(cat)

        query += " ORDER BY modelo ASC"
        cur.execute(query, params)
        # Enviamos los datos crudos para que el JS del navegador haga el redondeo y conversión
        return jsonify(cur.fetchall())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify([])
    finally: 
        conn.close()

@bp.route('/api/obtener_ventas')
def api_obtener_ventas():
    conn = database.get_db_connection()
    if not conn: return jsonify([])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT folio, fecha, cliente, total FROM ventas ORDER BY fecha DESC LIMIT 50")
        data = cur.fetchall()
        for d in data: 
            if isinstance(d['fecha'], datetime.date): d['fecha'] = d['fecha'].strftime("%d/%m/%Y")
        return jsonify(data)
    except: return jsonify([])
    finally: conn.close()

# APIs Tecnicos
@bp.route('/api/tecnicos/guardar_salida', methods=['POST'])
def guardar_salida_tecnico():
    data = request.json
    conn = database.get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO salidas_tecnicas (tecnicos, items, bobinas, estado, fecha) VALUES (%s, %s, %s, 'PENDIENTE', NOW()) RETURNING id""", (", ".join(data['tecnicos']), json.dumps(data['items']), json.dumps(data.get('bobinas', []))))
        sid = cur.fetchone()[0]
        for it in data['items']: cur.execute("UPDATE inventario_sucursal SET stock = stock - %s WHERE modelo = %s", (it['cantidad'], it['modelo']))
        conn.commit(); return jsonify({'status': 'success', 'folio': sid})
    except Exception as e: conn.rollback(); return jsonify({'status': 'error', 'message': str(e)})
    finally: conn.close()

@bp.route('/api/tecnicos/obtener_pendientes')
def obtener_pendientes():
    conn = database.get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try: cur.execute("SELECT * FROM salidas_tecnicas WHERE estado = 'PENDIENTE' ORDER BY fecha DESC"); return jsonify([{'id': r['id'], 'folio': r['folio'], 'tecnicos': r['tecnicos'], 'fecha': r['fecha'].strftime('%Y-%m-%d %H:%M'), 'items': r['items'], 'bobinas': r['bobinas'] if r['bobinas'] else []} for r in cur.fetchall()])
    except: return jsonify([])
    finally: conn.close()

@bp.route('/api/tecnicos/finalizar_servicio', methods=['POST'])
def finalizar_servicio():
    data = request.json; conn = database.get_db_connection(); cur = conn.cursor()
    try:
        for it in data['items']:
            dev = int(it['cantidad']) - int(it['usado_real'])
            if dev > 0: cur.execute("UPDATE inventario_sucursal SET stock = stock + %s WHERE modelo = %s", (dev, it['modelo']))
        cur.execute("UPDATE salidas_tecnicas SET items=%s, bobinas=%s, estado='FINALIZADO', observaciones=%s WHERE id=%s", (json.dumps(data['items']), json.dumps(data.get('bobinas', [])), data.get('observaciones', ''), data['id']))
        conn.commit(); return jsonify({'status': 'success'})
    finally: conn.close()

@bp.route('/api/tecnicos/historial')
def historial_tecnicos():
    conn = database.get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try: cur.execute("SELECT * FROM salidas_tecnicas WHERE estado = 'FINALIZADO' ORDER BY fecha DESC LIMIT 50"); return jsonify([{'fecha': r['fecha'].strftime('%d/%m/%Y'), 'folio': r['folio'], 'tecnicos': r['tecnicos'], 'items': r['items'], 'bobinas': r['bobinas']} for r in cur.fetchall()])
    except: return jsonify([])
    finally: conn.close()

@bp.route('/api/guardar_material_tecnico', methods=['POST'])
def guardar_material_tecnico():
    d = request.json; conn = database.get_db_connection(); cur = conn.cursor()
    try:
        for m in d.get('materiales', []):
            cur.execute("INSERT INTO reporte_tecnicos (tecnico, modelo, descripcion, cantidad, fecha) VALUES (%s, %s, %s, %s, NOW())", (d['tecnico'], m['modelo'], m['nombre'], m['cantidad']))
            if m.get('descontar'): cur.execute("UPDATE inventario_sucursal SET stock = stock - %s WHERE modelo = %s", (m['cantidad'], m['modelo']))
        conn.commit(); return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)})
    finally: conn.close()

@bp.route('/api/obtener_historial_tecnicos')
def api_historial_tecnicos():
    tecnico = request.args.get('tecnico', '').strip(); conn = database.get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor)
    query = "SELECT id, TO_CHAR(fecha, 'DD/MM/YYYY HH24:MI') as fecha, tecnico, modelo, descripcion, cantidad FROM reporte_tecnicos"
    if tecnico: query += f" WHERE tecnico ILIKE '%{tecnico}%'"
    cur.execute(query + " ORDER BY id DESC LIMIT 50"); data = cur.fetchall(); conn.close(); return jsonify(data)

@bp.route('/api/borrar_registro_tecnico', methods=['POST'])
def borrar_registro_tecnico():
    conn = database.get_db_connection(); cur = conn.cursor(); cur.execute("DELETE FROM reporte_tecnicos WHERE id = %s", (request.json.get('id'),)); conn.commit(); conn.close(); return jsonify({'status': 'success'})

# APIs Ordenes
@bp.route('/api/obtener_ordenes')
def api_obtener_ordenes():
    conn = database.get_db_connection(); cur = conn.cursor(cursor_factory=RealDictCursor); cur.execute("SELECT * FROM ordenes_trabajo ORDER BY id DESC"); data = cur.fetchall(); conn.close()
    for d in data: d['fecha_fmt'] = d['fecha'].strftime('%Y-%m-%d') if d['fecha'] else ""
    return jsonify(data)

@bp.route('/api/guardar_orden', methods=['POST'])
def api_guardar_orden():
    d = request.json; conn = database.get_db_connection(); cur = conn.cursor()
    try:
        if d.get('id'): cur.execute("UPDATE ordenes_trabajo SET folio=%s, cliente=%s, estatus=%s, pagado=%s, metodo_pago=%s, fecha=%s WHERE id=%s", (d['folio'], d['cliente'], d['estatus'], d['pagado'], d['metodo_pago'], d['fecha'], d['id']))
        else: cur.execute("INSERT INTO ordenes_trabajo (folio, cliente, estatus, pagado, metodo_pago, fecha) VALUES (%s, %s, %s, %s, %s, %s)", (d['folio'], d['cliente'], d['estatus'], d['pagado'], d['metodo_pago'], d['fecha']))
        conn.commit(); return jsonify({'status': 'success'})
    finally: conn.close()

@bp.route('/api/eliminar_orden', methods=['POST'])
def api_eliminar_orden():
    conn = database.get_db_connection(); cur = conn.cursor(); cur.execute("DELETE FROM ordenes_trabajo WHERE id=%s", (request.json['id'],)); conn.commit(); conn.close(); return jsonify({'status': 'success'})

# ==========================================
# 7. GENERADOR PDF
# ==========================================
class PDF(FPDF):
    def footer(self):
        self.set_y(-20)
        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        direccion = "Av. Araucarias 262 Fracc.Indeco Animas. Tel: (228) 690-7449, 819-79-01, 850-1380"
        web = "www.cyssxalapa.com.mx"
        direccion = direccion.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 5, direccion, 0, 1, 'C')
        self.cell(0, 5, web, 0, 0, 'C')

@bp.route('/api/exportar_pdf', methods=['POST'])
def exportar_pdf():
    # Esta es la ruta para el cotizador VIEJO (Laboratorio)
    # La mantenemos para que no truene si alguien la usa
    try:
        data = request.json
        cliente = data.get('cliente', 'MOSTRADOR').upper()
        items = data.get('items', [])
        total_str = data.get('total', '0.00')

        try:
            total_float = math.ceil(float(str(total_str).replace('$','').replace(',','')) / 5.0) * 5.0
        except: total_float = 0.0

        pdf = PDF()
        pdf.add_page()
        # (Lógica simplificada del viejo PDF para no saturar, pero funcional)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"COTIZACION (LEGACY): {cliente}", 0, 1, 'C')
        pdf.set_font('Arial', '', 10)
        for i in items:
            pdf.cell(0, 6, f"{i['cantidad']} x {i['nombre']} - {i['importe']}", 0, 1)
        pdf.ln(5)
        pdf.cell(0, 10, f"TOTAL: $ {total_float:,.2f}", 0, 1, 'R')
        
        nombre = f"Legacy_{cliente[:5]}.pdf"
        ruta = os.path.join('static', nombre)
        pdf.output(ruta)
        return jsonify({'status': 'success', 'archivo': f'/static/{nombre}'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)})
@bp.route('/garantias')
def garantias():
    # Ahora permite a admin y operador
    if 'user_id' not in session or session.get('rol') not in ['admin', 'operador']:
        return redirect(url_for('main.menu'))
    return render_template('garantias.html')

@bp.route('/api/garantias/obtener')
def api_obtener_garantias():
    conn = database.get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM garantias ORDER BY fecha_ingreso DESC")
    datos = cur.fetchall()
    conn.close()
    return jsonify(datos)

@bp.route('/api/garantias/guardar', methods=['POST'])
def api_guardar_garantia():
    data = request.json
    conn = database.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO garantias (folio, tipo_servicio, cliente, modelo, serie, accesorios, falla, sucursal_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (data['folio'], data['tipo_servicio'], data['cliente'], data['modelo'], 
              data['serie'], data['accesorios'], data['falla'], session.get('sucursal_id')))
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({'status': 'success', 'id': new_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        conn.close()

@bp.route('/imprimir_garantia/<int:id>')
def imprimir_garantia(id):
    conn = database.get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM garantias WHERE id = %s", (id,))
    g = cur.fetchone()
    conn.close()
    return render_template('ticket_garantia.html', g=g)

# --- AGREGAR ESTA RUTA AL FINAL DE routes.py ---

@bp.route('/api/inventario/exportar_pdf')
def exportar_inventario_pdf():
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat', 'TODAS')
    es_mario = session.get('username') == 'MARIO'

    conn = database.get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Consulta filtrada
    query = "SELECT * FROM inventario_sucursal WHERE 1=1"
    params = []
    if q:
        query += " AND (modelo ILIKE %s OR nombre ILIKE %s)"
        params.extend([f'%{q}%', f'%{q}%'])
    if cat != 'TODAS':
        query += " AND categoria = %s"
        params.append(cat)
    
    cur.execute(query, params)
    productos = cur.fetchall()
    conn.close()

    # Generar PDF
    pdf = FPDF(orientation='L', unit='mm', format='Letter')
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f'REPORTE DE EXISTENCIAS - CYSS ({"ARAUCARIAS" if es_mario else "GENERAL"})', 0, 1, 'C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Fecha: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.ln(5)

    # Encabezados: Ahora siempre mostramos ambas sucursales
    pdf.set_fill_color(0, 32, 96) 
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    
    # Definimos columnas fijas para todos
    cols = [('MODELO', 35), ('DESCRIPCION', 105), ('ARAUCARIAS', 25), ('AMERICAS', 25), ('CAT', 30)]

    for col in cols:
        pdf.cell(col[1], 8, col[0], 1, 0, 'C', True)
    pdf.ln()

    # Datos
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 8)
    for p in productos:
        pdf.cell(35, 7, str(p['modelo']), 1)
        pdf.cell(105, 7, str(p['nombre'])[:65], 1)
        pdf.cell(25, 7, str(p['stock']), 1, 0, 'C') # Stock Araucarias
        pdf.cell(25, 7, str(p['stock_americas']), 1, 0, 'C') # Stock Américas
        pdf.cell(30, 7, str(p['categoria']), 1, 0, 'C')
        pdf.ln()

    # Filas
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 9)
    for p in productos:
        pdf.cell(cols[0][1], 7, str(p['modelo']), 1)
        pdf.cell(cols[1][1], 7, str(p['nombre'])[:70], 1)
        pdf.cell(cols[2][1], 7, str(p['stock']), 1, 0, 'C')
        if not es_mario:
            pdf.cell(cols[3][1], 7, str(p['stock_americas']), 1, 0, 'C')
            pdf.cell(cols[4][1], 7, str(p['categoria']), 1, 0, 'C')
        else:
            pdf.cell(cols[3][1], 7, str(p['categoria']), 1, 0, 'C')
        pdf.ln()

    nombre_archivo = f"Inventario_{session.get('username')}_{datetime.datetime.now().strftime('%H%M%S')}.pdf"
    ruta = os.path.join('static', nombre_archivo)
    pdf.output(ruta)
    return jsonify({'status': 'success', 'url': f'/static/{nombre_archivo}'})
# ==========================================
# 8. RUTAS DE EDICIÓN Y CREACIÓN (INVENTARIO)
# ==========================================

@bp.route('/api/inventario/actualizar', methods=['POST'])
def api_actualizar_inventario():
    data = request.json
    conn = database.get_db_connection()
    
    if not conn:
        return jsonify({'status': 'error', 'message': 'Error de conexión a BD'})
        
    try:
        cur = conn.cursor()
        
        # Ahora recibimos el COSTO puro desde el modal de inventario.html
        costo_base = float(data.get('precio') or 0)
        stock_arau = int(data.get('stock_arau') or 0)
        stock_ame = int(data.get('stock_ame') or 0)
        
        cur.execute("""
            UPDATE inventario_sucursal 
            SET modelo=%s, nombre=%s, stock=%s, stock_americas=%s, precio=%s 
            WHERE id=%s
        """, (data['modelo'], data['nombre'], stock_arau, stock_ame, costo_base, data['id']))
        
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if conn: conn.close()

@bp.route('/api/crear_producto_manual', methods=['POST'])
def api_crear_producto_manual():
    data = request.json
    conn = database.get_db_connection()
    
    # --- ESCUDO: Si no hay conexión ---
    if not conn:
        return jsonify({'status': 'error', 'message': 'No se pudo conectar a la BD (Conflicto de Docker).'})
        
    try:
        cur = conn.cursor()
        
        modelo = data['modelo'].strip()
        nombre = data['nombre'].strip()
        proveedor = data.get('proveedor', 'GENERICO')
        moneda = data.get('moneda', 'MXN')
        nuevo_precio = float(data.get('precio') or 0)
        
        # Asignar stock a la sucursal correcta
        sucursal_destino = data.get('sucursal', 'ARAUCARIAS')
        stock_ingreso = int(data.get('stock') or 0)
        
        stock_arau_add = stock_ingreso if sucursal_destino == 'ARAUCARIAS' else 0
        stock_ame_add = stock_ingreso if sucursal_destino == 'AMERICAS' else 0
        
        # 1. Verificar existencia
        cur.execute("SELECT id, precio, stock, stock_americas FROM inventario_sucursal WHERE modelo = %s", (modelo,))
        producto_existente = cur.fetchone()
        
        if producto_existente:
            # Lógica de Actualización (Protección de precio más alto)
            precio_actual = float(producto_existente[1] or 0)
            precio_final = nuevo_precio if nuevo_precio > precio_actual else precio_actual
            
            stock_arau_final = int(producto_existente[2] or 0) + stock_arau_add
            stock_ame_final = int(producto_existente[3] or 0) + stock_ame_add
            
            cur.execute("""
                UPDATE inventario_sucursal 
                SET nombre=%s, proveedor=%s, moneda=%s, precio=%s, stock=%s, stock_americas=%s
                WHERE modelo=%s
            """, (nombre, proveedor, moneda, precio_final, stock_arau_final, stock_ame_final, modelo))
            
        else:
            # Lógica de Inserción
            cur.execute("""
                INSERT INTO inventario_sucursal (modelo, nombre, proveedor, moneda, precio, stock, stock_americas) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (modelo, nombre, proveedor, moneda, nuevo_precio, stock_arau_add, stock_ame_add))
            
        conn.commit()
        return jsonify({'status': 'success'})
        
    except Exception as e:
        if conn: conn.rollback() # Escudo para el rollback
        print(f"ERROR CREAR PRODUCTO: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if conn: conn.close()