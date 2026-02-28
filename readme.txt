📄 LEEME.txt (Manual de Portabilidad CYSS V12)
Este manual garantiza que puedas mover el sistema a cualquier computadora sin perder la configuración de usuarios, sucursales ni lógica de permisos.

1. REQUISITOS PREVIOS
Tener instalado Docker y Docker Desktop.

Tener tu carpeta de proyecto PUNTODEVENTA con los archivos actualizados:

database.py (Versión unificada con nombre_usuario y nombre_comercial).

routes.py (Con lógica de PDF y login corregida).

templates/menu.html (Con el parche de roles para Mario).

inventario_definitivo.csv (Tu lista de productos limpia).

2. PASOS PARA INSTALAR EN UNA NUEVA PC
Si cambias de equipo, sigue este orden exacto:

Levantar Contenedores:

Bash
docker-compose up -d
Sincronizar Código:
Asegúrate de que Docker tenga tus archivos de Windows (esto no borra la base de datos):

Bash
docker cp ./routes.py cyss_app:/app/routes.py
docker cp ./templates/menu.html cyss_app:/app/templates/menu.html
Ejecutar Reparación Segura:
Este comando creará las sucursales y usuarios (Jared/Mario) automáticamente si no existen, sin borrar tus datos previos:

Bash
docker exec cyss_app python3 database.py
Cargar Inventario:
Usa tu archivo limpio para llenar el almacén:

Bash
cat inventario_definitivo.csv | docker exec -i cyss_app sh -c 'cat > /app/maestro.csv'
docker exec cyss_app python3 inspector.py
3. REGLAS DE ORO PARA NO PERDER DATOS
NUNCA uses el comando docker-compose down -v. El -v borra los discos virtuales donde vive tu base de datos. Usa solo docker-compose down o docker stop.

Caché: Si haces un cambio en el código y no se ve, presiona Ctrl + F5 en el navegador.

Login: Los usuarios siempre son Jared (Admin) y Mario (Limitado). La contraseña es Cyss2017.