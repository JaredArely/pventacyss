import requests
import config 

# --- CORRECCIÓN: Definimos la función aquí (SIN importar de database) ---
def redondear_cyss(valor):
    if valor is None:
        return 0.0
    try:
        return round(float(valor), 2)
    except Exception:
        return 0.0
# ----------------------------------------------------------------------

def obtener_access_token():
    url = "https://developers.syscom.mx/oauth/token"
    payload = {
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        response = requests.post(url, data=payload, timeout=5, verify=False)
        if response.status_code == 200:
            return response.json()['access_token']
    except Exception as e:
        print(f"--- ❌ ERROR TOKEN: {e} ---")
    return None

def buscar_syscom_api(query, dolar_usuario=None):
    token = obtener_access_token()
    if not token: return []
    
    tc_final = float(dolar_usuario) if dolar_usuario and float(dolar_usuario) > 0 else config.TIPO_CAMBIO_DOLAR

    url = f"https://developers.syscom.mx/api/v1/productos?busqueda={query}"
    headers = {"Authorization": f"Bearer {token}"}
    resultados = []
    
    try:
        print(f"--- 🚀 CONSULTANDO SYSCOM: {query} | TC: {tc_final} ---")
        r = requests.get(url, headers=headers, timeout=8, verify=False)
        
        if r.status_code == 200:
            data = r.json()
            productos = data.get('productos', [])
            
            for p in productos[:20]: 
                modelo = p.get('modelo', '').upper()
                posibles_precios = [float(p.get('precio_descuento', 0) or 0), float(p.get('precio_especial', 0) or 0), float(p.get('precio_lista', 0) or 0)]
                sub = p.get('precios', {})
                posibles_precios.append(float(sub.get('precio_descuento', 0) or 0))
                posibles_precios.append(float(sub.get('precio_lista', 0) or 0))

                precios_validos = [x for x in posibles_precios if x > 0.1]
                costo_usd = min(precios_validos) if precios_validos else 0.0

                costo_ajustado_mxn = costo_usd * config.FACTOR_FORMULA * tc_final
                
                # Usamos la función local
                precio_publico = redondear_cyss(costo_ajustado_mxn / config.MARGEN_PUBLICO)
                precio_preferente = redondear_cyss(costo_ajustado_mxn / config.MARGEN_PREFERENTE)
                precio_integrador = redondear_cyss(costo_ajustado_mxn / config.MARGEN_INTEGRADOR)

                etiqueta_stock = "WEB" if costo_usd > 0 else "SIN PRECIO"

                resultados.append({
                    'modelo': modelo,
                    'titulo': p.get('titulo', ''),
                    'precio_lista': costo_usd,
                    'precio': precio_publico,
                    'precio_venta': precio_publico,
                    'precio_usd': precio_publico,
                    'precios': {'publico': precio_publico, 'preferente': precio_preferente, 'integrador': precio_integrador},
                    'stock_label': etiqueta_stock,
                    'img_portada': p.get('img_portada', '/static/logocyss.png'),
                    'origen': 'SYSCOM',
                    'moneda': 'USD'
                })
    except Exception as e:
        print(f"--- ERROR API: {e} ---")
    return resultados