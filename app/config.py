import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una-clave-secreta-muy-dificil-de-adivinar'
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'panthera.db')
    LOG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'app.log')
    JOBS_BASE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'jobs_output')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuraciones personalizadas de Panthera
    PANTHERA_TOOLS_CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'utils', 'tools_config.json') # Ejemplo
    PANTHERA_PROFILES_CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'utils', 'profiles_config.json') # Ejemplo

class DevelopmentConfig(Config):
    DEBUG = True
    # Aquí se podrían sobreescribir o añadir configuraciones específicas para desarrollo

class ProductionConfig(Config):
    DEBUG = False
    # Aquí se podrían sobreescribir o añadir configuraciones específicas para producción

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'test_panthera.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    JOBS_BASE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'test_jobs_output')
    # Asegurarse de que las pruebas no usen la misma base de datos o archivos que desarrollo/producción

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}