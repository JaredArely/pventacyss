from flask import Flask
from routes import bp 
import database

app = Flask(__name__)

# Activamos la seguridad de 2026
app.secret_key = 'cyss_clave_maestra_2026' 
app.config['TEMPLATES_AUTO_RELOAD'] = True

app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)