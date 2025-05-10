import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'una-clave-secreta-muy-dificil-de-adivinar'
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'panthera.db')
    LOG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'app.log')
    JOBS_BASE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'jobs_output')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PANTHERA_TOOLS_CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'utils', 'tools_config.json') # Ejemplo
    PANTHERA_PROFILES_CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'utils', 'profiles_config.json') # Ejemplo

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'test_panthera.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    JOBS_BASE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance', 'test_jobs_output')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}