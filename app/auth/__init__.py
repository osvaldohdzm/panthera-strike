from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from . import routes, models # Importar rutas y modelos del Blueprint