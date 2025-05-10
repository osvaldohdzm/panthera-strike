from flask import Blueprint

jobs_bp = Blueprint('jobs', __name__)

from . import routes, services, repository # Importar componentes del Blueprint