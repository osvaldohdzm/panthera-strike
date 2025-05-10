from flask import Flask
from .config import Config  # Suponiendo que config.py estará en el mismo directorio 'app'
from .extensions import login_manager, db # Suponiendo que extensions.py existe
# Importar Blueprints más adelante cuando se creen
# from .auth.routes import auth_bp
# from .main.routes import main_bp
# from .jobs.routes import jobs_bp

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True) # Para configuraciones de instancia

    # Inicializar extensiones de Flask
    login_manager.init_app(app)
    # db.init_app(app) # Si se usa SQLAlchemy u otro ORM

    # Registrar Blueprints
    # app.register_blueprint(auth_bp, url_prefix='/auth')
    # app.register_blueprint(main_bp)
    # app.register_blueprint(jobs_bp, url_prefix='/api')

    # Configuración de logging (opcional, se puede mejorar)
    if not app.debug and not app.testing:
        # ... configuraciones de logging para producción ...
        pass

    # Ejemplo de una ruta simple para verificar que la app funciona
    @app.route('/hello')
    def hello():
        return 'Hello, World from create_app!'

    return app