from flask import Blueprint, render_template, jsonify, current_app, send_from_directory, request, g
from flask_login import login_required, current_user
import os
import json
from . import main_bp
from app.database import get_db # Para interactuar con la base de datos
from utils import helpers # Para cargar configuraciones de herramientas/perfiles

@main_bp.route('/')
@login_required
def index():
    # Lógica para la página principal, por ejemplo, mostrar el dashboard o la página de escaneos.
    # Esto podría ser similar a la ruta '/scans' del app.py original.
    return render_template('scans.html', current_user=current_user) # Asegurarse que scans.html existe

@main_bp.route('/api/config', methods=['GET'])
@login_required
def get_app_config():
    # Devuelve la configuración de herramientas y perfiles
    # Esto es similar a la ruta '/api/config' del app.py original
    try:
        tools = helpers.load_tools_config()
        profiles = helpers.load_profiles_config()
        scan_phases = helpers.SCAN_PHASES
        return jsonify({
            "tools": tools,
            "profiles": profiles,
            "scan_phases": scan_phases
        })
    except Exception as e:
        current_app.logger.error(f"Error al cargar la configuración: {e}")
        return jsonify({"error": "Error al cargar la configuración de la aplicación"}), 500

# Servir archivos estáticos de Vue (si se usa Vue y se construye en 'dist')
# Esta parte puede necesitar ajustes dependiendo de cómo se integre el frontend
@main_bp.route('/app/', defaults={'path': ''})
@main_bp.route('/app/<path:path>')
@login_required
def serve_vue_app(path):
    vue_dist_path = os.path.join(current_app.static_folder, 'dist')
    if path != "" and os.path.exists(os.path.join(vue_dist_path, path)):
        return send_from_directory(vue_dist_path, path)
    else:
        return send_from_directory(vue_dist_path, 'index.html')


# Ejemplo de cómo se podría manejar el contexto global 'g' si es necesario
# @main_bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get('user_id') # O como se maneje la sesión
#     if user_id is None:
#         g.user = None
#     else:
#         # Cargar usuario desde la base de datos
#         # g.user = get_db().execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
#         g.user = current_user # Si se usa Flask-Login, current_user ya está disponible

# Ruta para favicon (ejemplo, si no se maneja de otra forma)
@main_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'images'),
                               'panthera_logo.png', mimetype='image/png') # Ajustar ruta y nombre del archivo