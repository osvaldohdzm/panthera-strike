from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy # Si se decide usar SQLAlchemy

login_manager = LoginManager()
# Configuración de login_manager (ej. vista de login, mensaje de no autenticado)
login_manager.login_view = 'auth.login' # Suponiendo que el Blueprint de auth se llamará 'auth'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Por favor, inicie sesión para acceder a esta página.'

# db = SQLAlchemy() # Descomentar y configurar si se usa SQLAlchemy