from flask import Flask, request, jsonify, render_template, send_file, current_app, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import datetime
import json
import threading
from scanner.engine import run_scan
from utils import create_job_directories, get_scan_status, get_job_logs, get_tool_config, list_all_jobs
import shutil # Para crear archivos ZIP

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Necesario para Flask-Login y sesiones

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Vista a la que redirigir si se requiere login
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

# Base de datos SQLite para usuarios
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Acceder a columnas por nombre
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        # Crear usuario por defecto si no existe
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", ('juno',))
        if cursor.fetchone() is None:
            hashed_password = generate_password_hash('domino', method='pbkdf2:sha256')
            cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", ('juno', hashed_password))
            db.commit()
            print("Usuario por defecto 'pantherysyar' creado.")

# Modelo de Usuario para Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return User(id=user_data['id'], username=user_data['username'])
    return None

# Crear el archivo schema.sql si no existe (para la tabla de usuarios)
SCHEMA_SQL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
if not os.path.exists(SCHEMA_SQL_PATH):
    with open(SCHEMA_SQL_PATH, 'w') as f:
        f.write("""
DROP TABLE IF EXISTS user;
CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);
""")
    print("schema.sql creado.")

# Inicializar la base de datos al arrancar la aplicación
# Esto se debe hacer dentro del contexto de la aplicación
with app.app_context():
    from flask import g # Importar g aquí para evitar problemas de contexto
    init_db()

# Directorio para almacenar los resultados de los escaneos
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

# Almacenamiento en memoria para el estado de los trabajos (para MVP)
# En un sistema real, esto debería ser una base de datos o un sistema de colas más robusto
active_jobs = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        if user_data and check_password_hash(user_data['password'], password):
            user = User(id=user_data['id'], username=user_data['username'])
            login_user(user)
            flash('Inicio de sesión exitoso.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Credenciales incorrectas. Inténtalo de nuevo.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/tools', methods=['GET'])
def get_tools_route():
    config = get_tool_config()
    # Devolver solo la lista de herramientas y los presets para el frontend
    return jsonify({'tools': config['tools'], 'presets': config['presets']})

@app.route('/jobs', methods=['GET'])
def list_jobs_route():
    job_ids = list_all_jobs(RESULTS_DIR)
    jobs_data = []
    for job_id in job_ids:
        status_info = get_scan_status(job_id, active_jobs, RESULTS_DIR)
        if status_info:
            jobs_data.append({
                'id': job_id,
                'status': status_info.get('status', 'unknown'),
                'start_time': status_info.get('start_time', 'N/A'),
                'targets': status_info.get('targets', [])
            })
        else:
            # Si no hay summary.json, al menos listar el ID
            jobs_data.append({
                'id': job_id,
                'status': 'unknown',
                'start_time': 'N/A',
                'targets': []
            })
    return jsonify(jobs_data)

@app.route('/scan', methods=['POST'])
def start_scan_route():
    data = request.json
    targets = data.get('targets')
    selected_tool_ids = data.get('tools') # Nueva entrada para herramientas seleccionadas

    if not targets:
        return jsonify({'error': 'No targets provided'}), 400

    if not isinstance(targets, list):
        targets = [t.strip() for t in targets.split('\n') if t.strip()]

    if not targets:
        return jsonify({'error': 'No valid targets provided after parsing'}), 400

    job_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    job_path, targets_file_path = create_job_directories(RESULTS_DIR, job_id, targets)

    # Iniciar el escaneo en un hilo separado para no bloquear la API
    # Pasar selected_tool_ids a run_scan
    scan_thread = threading.Thread(target=run_scan, args=(job_id, targets, job_path, targets_file_path, active_jobs, selected_tool_ids))
    scan_thread.start()

    active_jobs[job_id] = {'status': 'pending', 'targets': targets, 'start_time': datetime.datetime.now().isoformat(), 'logs': [], 'results_path': job_path, 'selected_tools': selected_tool_ids}

    return jsonify({'message': 'Scan job started', 'job_id': job_id, 'status_url': f'/status/{job_id}'}), 202

@app.route('/api/jobs', methods=['GET'])
def api_get_jobs():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        return jsonify([])

    job_ids = list_all_jobs(RESULTS_DIR)
    jobs_with_details = []
    for job_id in job_ids:
        status_info = get_scan_status(job_id, active_jobs, RESULTS_DIR)
        if status_info:
            jobs_with_details.append({
                "id": job_id,
                "status": status_info.get("status", "unknown"),
                "timestamp": status_info.get("start_time", "N/A"),
                "zip_path": f"/api/results/download/{job_id}" if status_info.get("status") == "COMPLETED" else None
            })
        else:
            jobs_with_details.append({
                "id": job_id,
                "status": "unknown (no summary)",
                "timestamp": "N/A",
                "zip_path": None
            })

    return jsonify(jobs_with_details)

@app.route('/status/<job_id>', methods=['GET'])
def get_status_route(job_id):
    status_info = get_scan_status(job_id, active_jobs, RESULTS_DIR)
    if not status_info:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(status_info)

@app.route('/logs/<job_id>', methods=['GET'])
def get_logs_route(job_id):
    log_content = get_job_logs(job_id, RESULTS_DIR)
    if log_content is None:
        return jsonify({'error': 'Logs not found or job does not exist'}), 404
    return jsonify({'job_id': job_id, 'logs': log_content})

@app.route('/download_job/<job_id>', methods=['GET'])
def download_job_results(job_id):
    job_path = os.path.join(RESULTS_DIR, job_id)
    if not os.path.isdir(job_path):
        return jsonify({'error': 'Job directory not found'}), 404

    # Crear un archivo ZIP temporal
    # Usar un directorio temporal dentro de la instancia de la app si es posible, o en /tmp
    # Para simplificar, lo crearemos en el directorio de resultados y lo limpiaremos
    zip_filename_base = f"job_{job_id}_results"
    zip_path_base = os.path.join(RESULTS_DIR, zip_filename_base) # Base para el nombre del archivo zip

    try:
        # shutil.make_archive devuelve la ruta completa al archivo zip creado
        zip_file_path = shutil.make_archive(zip_path_base, 'zip', job_path)
    except Exception as e:
        current_app.logger.error(f"Error creating zip file for job {job_id}: {e}")
        return jsonify({'error': f'Could not create zip file: {str(e)}'}), 500

    try:
        return send_file(zip_file_path, as_attachment=True, download_name=f"{zip_filename_base}.zip", mimetype='application/zip')
    finally:
        # Limpiar el archivo ZIP después de enviarlo
        if os.path.exists(zip_file_path):
            try:
                os.remove(zip_file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting temporary zip file {zip_file_path}: {e}")

if __name__ == '__main__':
    # Asegurarse de que g esté disponible en el contexto de la aplicación para init_db
    from flask import g
    app.run(host='0.0.0.0', port=5000, debug=True)