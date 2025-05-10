import os
from flask import Flask
from .config import Config
from .extensions import db, login_manager # Asegúrate que el orden sea consistente o no importa

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True) # Para configuraciones de instancia

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    login_manager.init_app(app)


    if not app.debug and not app.testing:
        pass

    @app.route('/hello')
    def hello():
        return 'Hello, World from create_app!'

    return app