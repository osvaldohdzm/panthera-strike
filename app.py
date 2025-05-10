import logging
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_file,
    redirect,
    url_for,
    flash,
    g,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import datetime
import json
import threading
import shutil
from pathlib import Path
import time
import re
import subprocess
import shlex # Importado para citar argumentos de comandos

from utils import helpers # Asegurar que la importación es correcta


def run_scan_process(
    job_id,
    job_path,
    targets,
    selected_tools_config_list, # Lista de {id: "tool_id", cli_params: {}}
    advanced_options,
    db_path_for_thread,
    tool_definitions_for_thread, # Diccionario completo de TOOLS_CONFIG
    app_logger, # Nombre del parámetro
):
    app_logger.info(f"Motor de escaneo iniciado para job {job_id} en {job_path}")

    tool_outputs_dir = Path(job_path) / "tool_outputs"
    os.makedirs(tool_outputs_dir, exist_ok=True)

    job_summary_path = Path(job_path) / "summary.json"
    current_summary_data = helpers.get_scan_status_from_file(job_path) # Cargar estado actual

    try:
        with sqlite3.connect(db_path_for_thread) as conn_status_update:
            current_time_iso = datetime.datetime.now().isoformat()
            conn_status_update.execute(
                "UPDATE job SET status = ?, start_timestamp = ? WHERE id = ?",
                ("RUNNING", current_time_iso, job_id),
            )
            conn_status_update.commit()
        
        current_summary_data["status"] = "RUNNING"
        current_summary_data["start_timestamp"] = current_time_iso
        current_summary_data["logs"].append({
            "timestamp": current_time_iso,
            "message": f"Job {job_id} ha comenzado a ejecutarse.",
            "level": "info", "is_html": False # Coincidir con frontend
        })
        helpers.save_job_summary(job_path, current_summary_data)
    except Exception as e_status:
        app_logger.error(f"Job {job_id}: Error al actualizar estado a RUNNING: {e_status}", exc_info=True)

    total_tools_to_run = len(targets) * len(selected_tools_config_list)
    completed_tools_count = 0
    
    conn_thread = sqlite3.connect(db_path_for_thread)
    conn_thread.row_factory = sqlite3.Row
    final_job_status_engine = "ERROR" # Estado por defecto si el motor falla

    try:
        for target_idx, target_item in enumerate(targets):
            target_value = target_item # Asumimos que targets es una lista de strings

            for tool_config_entry in selected_tools_config_list:
                tool_id = tool_config_entry["id"]
                user_cli_params_for_tool = tool_config_entry.get("cli_params", {})
                tool_definition = tool_definitions_for_thread.get(tool_id)

                if not tool_definition:
                    app_logger.warning(f"Job {job_id}: Definición no encontrada para herramienta {tool_id}. Saltando.")
                    current_summary_data["logs"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Definición no encontrada para herramienta {tool_id}. Saltando.",
                        "level": "warn", "is_html": False
                    })
                    completed_tools_count += 1 # Contar como "procesada" para el progreso
                    continue

                cursor_cancel = conn_thread.cursor()
                cursor_cancel.execute("SELECT status FROM job WHERE id = ?", (job_id,))
                job_status_db_check = cursor_cancel.fetchone()
                cursor_cancel.close()

                if job_status_db_check and job_status_db_check["status"] in ["REQUEST_CANCEL", "CANCELLED"]:
                    app_logger.info(f"Cancelación detectada para job {job_id}. Herramienta {tool_id} en {target_value} no se ejecutará.")
                    current_summary_data["logs"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Escaneo cancelado antes de ejecutar {tool_definition.get('name', tool_id)} en {target_value}.",
                        "level": "warn", "is_html": False
                    })
                    final_job_status_engine = "CANCELLED"
                    conn_thread.close()
                    return final_job_status_engine

                tool_output_filename_base = f"{tool_id}_{target_value.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}"
                
                command_template = tool_definition.get("command_template", "")
                if not command_template:
                    app_logger.warning(f"Job {job_id}: No command template for tool {tool_id}")
                    completed_tools_count += 1
                    continue

                final_command = command_template
                
                final_command = final_command.replace("{target}", shlex.quote(target_value))
                final_command = final_command.replace("{target_domain}", shlex.quote(target_value)) # Asumir que target_value es el dominio si es el placeholder
                final_command = final_command.replace("{target_url}", shlex.quote(target_value)) # Asumir que target_value es la URL
                final_command = final_command.replace("{target_host_or_ip}", shlex.quote(target_value))
                final_command = final_command.replace("{target_ip_range}", shlex.quote(target_value))
                final_command = final_command.replace("{target_domain_or_ip}", shlex.quote(target_value))
                final_command = final_command.replace("{target_wordpress_url}", shlex.quote(target_value))
                final_command = final_command.replace("{target_joomla_url}", shlex.quote(target_value))
                final_command = final_command.replace("{target_url_with_params}", shlex.quote(target_value)) # El usuario debe proveer la URL completa con params
                final_command = final_command.replace("{target_url_with_lfi_fuzz_param}", shlex.quote(target_value)) # El usuario debe proveer la URL con FUZZ

                final_command = final_command.replace("{output_file}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.txt"))) # Default a .txt
                final_command = final_command.replace("{output_file_base}", shlex.quote(str(tool_outputs_dir / tool_output_filename_base)))
                final_command = final_command.replace("{output_file_json}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.json")))
                final_command = final_command.replace("{output_file_xml}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.xml")))
                final_command = final_command.replace("{output_file_dir}", shlex.quote(str(tool_outputs_dir)))



                temp_command_parts = []
                base_cmd_tool = final_command.split(" ")[0] # Obtener el ejecutable
                temp_command_parts.append(base_cmd_tool)

                remaining_template = " ".join(final_command.split(" ")[1:])
                
                for p_key, p_val in user_cli_params_for_tool.items():
                    if p_val is not None and str(p_val).strip() != "":
                        remaining_template = remaining_template.replace(f"{{{p_key}}}", shlex.quote(str(p_val)))

                if tool_definition.get("cli_params_config"):
                    for p_conf in tool_definition["cli_params_config"]:
                        placeholder = f"{{{p_conf['name']}}}"
                        if placeholder in remaining_template: # Si aún existe el placeholder
                            default_val = p_conf.get("default")
                            if default_val is not None and str(default_val).strip() != "":
                                remaining_template = remaining_template.replace(placeholder, shlex.quote(str(default_val)))
                
                try:
                    remaining_template = re.sub(r"\{[a-zA-Z0-9_]+\}", "", remaining_template)
                    remaining_template = ' '.join(remaining_template.split()) # Limpiar espacios múltiples
                    
                    if not tool_definition.get("needs_shell", False):
                        final_command_list = [base_cmd_tool] + shlex.split(remaining_template)
                        final_command_str_for_log = " ".join(final_command_list)
                    else:
                        final_command_str_for_log = base_cmd_tool + " " + remaining_template
                        final_command_list = final_command_str_for_log # Se pasa como cadena a Popen

                except ValueError as e_shlex: # Error en shlex.split (e.g. comillas no cerradas)
                    app_logger.error(f"Job {job_id}: Error al parsear argumentos para {tool_id}: {e_shlex}. Comando: {base_cmd_tool + ' ' + remaining_template}")
                    completed_tools_count += 1
                    continue
                

                app_logger.info(f"Job {job_id}: Ejecutando [{tool_id}] en [{target_value}]: {final_command_str_for_log}")
                current_summary_data["logs"].append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": f"Ejecutando: {final_command_str_for_log}",
                    "level": "command", "is_html": False
                })
                
                tool_prog_key = f"{tool_id}_on_{target_value}" # Clave única
                current_summary_data["tool_progress"][tool_prog_key] = {
                    "name": tool_definition.get("name", tool_id), # Nombre legible
                    "status": "running",
                    "command": final_command_str_for_log,
                    "start_time": datetime.datetime.now().isoformat(),
                    "output_file": None, # Se actualizará después
                    "error_message": None
                }
                helpers.save_job_summary(job_path, current_summary_data)

                tool_run_status = "error"
                tool_error_message = ""
                actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.txt" # Default, puede cambiar

                if "{output_file_json}" in tool_definition.get("command_template", ""):
                    actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.json"
                elif "{output_file_xml}" in tool_definition.get("command_template", ""):
                    actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.xml"
                elif "{output_file_dir}" in tool_definition.get("command_template", ""):
                    actual_output_file_path = tool_outputs_dir # O un archivo específico si la herramienta lo crea predeciblemente


                try:
                    process_args = final_command_list if not tool_definition.get("needs_shell", False) else final_command_str_for_log
                    process = subprocess.run(
                        process_args,
                        shell=tool_definition.get("needs_shell", False),
                        capture_output=True, # Siempre capturar para logging
                        text=True,
                        timeout=int(advanced_options.get("tool_timeout", tool_definition.get("timeout", 3600))),
                        check=False, # No lanzar excepción por returncode != 0
                        cwd=str(tool_outputs_dir) # Ejecutar desde el directorio de salida de la herramienta
                    )

                    raw_log_path = tool_outputs_dir / f"{tool_output_filename_base}_raw.log"
                    with open(raw_log_path, "w", encoding="utf-8") as f_raw:
                        f_raw.write(f"--- Command ---\n{final_command_str_for_log}\n\n")
                        f_raw.write(f"--- Return Code: {process.returncode} ---\n\n")
                        f_raw.write(f"--- STDOUT ---\n{process.stdout or '<no stdout>'}\n\n")
                        f_raw.write(f"--- STDERR ---\n{process.stderr or '<no stderr>'}\n\n")

                    if not any(p in tool_definition.get("command_template", "") for p in ["{output_file}", "{output_file_base}", "{output_file_json}", "{output_file_xml}", "{output_file_dir}"]):
                        if process.stdout: # Solo si hay stdout
                             with open(actual_output_file_path, "w", encoding="utf-8") as f_tool_out:
                                f_tool_out.write(process.stdout)


                    if process.returncode == 0:
                        tool_run_status = "completed"
                        current_summary_data["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"{tool_definition.get('name', tool_id)} en {target_value} completado.",
                            "level": "success", "is_html": False
                        })
                    else:
                        tool_run_status = "error"
                        tool_error_message = f"Exit code {process.returncode}. Stderr: {process.stderr[:250]}..." if process.stderr else f"Exit code {process.returncode}."
                        current_summary_data["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Error en {tool_definition.get('name', tool_id)} en {target_value}: {tool_error_message}",
                            "level": "error", "is_html": False
                        })
                
                except subprocess.TimeoutExpired:
                    tool_run_status = "error"
                    tool_error_message = "Timeout Expirado"
                    app_logger.warning(f"Job {job_id}: Timeout para {tool_id} en {target_value}.")
                    current_summary_data["logs"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Timeout para {tool_definition.get('name', tool_id)} en {target_value}.",
                        "level": "error", "is_html": False
                    })
                    try:
                        with open(actual_output_file_path, "a", encoding="utf-8") as f_out_timeout:
                            f_out_timeout.write("\n\n--- ERROR: TIMEOUT EXPIRED ---")
                    except Exception: # Si el archivo no existe o no se puede escribir
                        pass


                except Exception as e_tool_exec:
                    tool_run_status = "error"
                    tool_error_message = str(e_tool_exec)
                    app_logger.error(f"Job {job_id}: Excepción ejecutando {tool_id} en {target_value}: {e_tool_exec}", exc_info=True)
                    current_summary_data["logs"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Excepción en {tool_definition.get('name', tool_id)} en {target_value}: {e_tool_exec}",
                        "level": "error", "is_html": False
                    })
                    try:
                        with open(actual_output_file_path, "a", encoding="utf-8") as f_out_exc:
                           f_out_exc.write(f"\n\n--- EXCEPTION: {e_tool_exec} ---")
                    except Exception:
                        pass


                completed_tools_count += 1
                current_progress = int((completed_tools_count / total_tools_to_run) * 100) if total_tools_to_run > 0 else 0
                
                output_file_to_report = None
                if Path(actual_output_file_path).is_file() and Path(actual_output_file_path).stat().st_size > 0 : # Solo reportar si el archivo existe y no está vacío
                    output_file_to_report = str(Path(actual_output_file_path).name)
                elif Path(actual_output_file_path).is_dir(): # Si es un directorio
                     output_file_to_report = str(Path(actual_output_file_path).name) + "/" # Indicar que es un dir

                current_summary_data["tool_progress"][tool_prog_key].update({
                    "status": tool_run_status,
                    "output_file": output_file_to_report,
                    "end_time": datetime.datetime.now().isoformat(),
                    "error_message": tool_error_message if tool_error_message else None,
                })
                current_summary_data["overall_progress"] = current_progress
                helpers.save_job_summary(job_path, current_summary_data)

                try: # Actualizar progreso en DB
                    conn_thread.execute(
                        "UPDATE job SET overall_progress = ? WHERE id = ?",
                        (current_progress, job_id),
                    )
                    conn_thread.commit()
                except Exception as e_db_prog:
                    app_logger.error(f"Job {job_id}: Error al actualizar progreso en DB: {e_db_prog}", exc_info=True)
        
        final_job_status_engine = "COMPLETED"
        if any(tp.get("status") == "error" for tp in current_summary_data.get("tool_progress", {}).values()):
            final_job_status_engine = "COMPLETED_WITH_ERRORS"

    except Exception as e_main_engine:
        app_logger.error(f"Error mayor en el motor de escaneo para job {job_id}: {e_main_engine}", exc_info=True)
        current_summary_data["logs"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "message": f"Error crítico del motor: {e_main_engine}",
            "level": "error", "is_html": False
        })
        current_summary_data["error_message"] = str(e_main_engine)
        final_job_status_engine = "ERROR"
    finally:
        current_summary_data["status"] = final_job_status_engine
        current_summary_data["end_timestamp"] = datetime.datetime.now().isoformat()
        if final_job_status_engine != "CANCELLED": # No sobrescribir progreso si se canceló
            current_summary_data["overall_progress"] = 100 # Marcar como 100% al finalizar (o cancelar)
        
        helpers.save_job_summary(job_path, current_summary_data) # Guardado final del summary
        if conn_thread:
            conn_thread.close()
            
    return final_job_status_engine


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.config["DATABASE"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panthera.db")
app.config["RESULTS_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_results")
app.config["MAX_PARALLEL_THREADS_PER_JOB"] = int(os.environ.get("MAX_PARALLEL_THREADS_PER_JOB", 1)) # No se usa actualmente

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

active_scan_threads = {} # job_id: threading.Thread object

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db_command():
    db = get_db()
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with app.open_resource(schema_path, mode="r") as f:
        db.cursor().executescript(f.read())
    db.commit()
    app.logger.info("Base de datos inicializada.")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE username = ?", ("panthera",))
    if cursor.fetchone() is None:
        hashed_password = generate_password_hash("panthera", method="pbkdf2:sha256")
        cursor.execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("panthera", hashed_password),
        )
        db.commit()
        app.logger.info("Usuario por defecto 'panthera' creado.")

@app.cli.command("init-db")
def init_db_cli():
    init_db_command()

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cur = db.execute("SELECT * FROM user WHERE id = ?", (user_id,))
    user_data = cur.fetchone()
    if user_data:
        return User(id=user_data["id"], username=user_data["username"])
    return None

os.makedirs(app.config["RESULTS_DIR"], exist_ok=True)

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        cur = db.execute("SELECT * FROM user WHERE username = ?", (username,))
        user_data = cur.fetchone()
        if user_data and check_password_hash(user_data["password"], password):
            user_obj = User(id=user_data["id"], username=user_data["username"])
            login_user(user_obj)
            flash("Inicio de sesión exitoso.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "danger")
    return render_template("login.html", script_root=request.script_root)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("scans.html", script_root=request.script_root)


@app.route("/api/config", methods=["GET"])
@login_required
def get_app_config_route():
    try:
        config_data = {
            "tools": helpers.get_tools_definition(),
            "profiles": helpers.get_scan_profiles(),
            "phases": helpers.get_pentest_phases(),
            "script_root": request.script_root, # Para que JS sepa la raíz de la app
        }
        return jsonify(config_data)
    except Exception as e:
        app.logger.error(f"Error al cargar configuración: {e}", exc_info=True)
        return jsonify({"error": "No se pudo cargar la configuración del servidor."}), 500


def scan_job_thread_target(
    job_id,
    job_path,
    targets,
    selected_tools_config, # Lista de {id: "tool_id", cli_params: {}}
    advanced_options,
    db_path, # app.config["DATABASE"]
    tool_definitions, # helpers.get_tools_definition()
    app_logger_for_thread,
):
    final_status_from_engine = "ERROR" # Default
    error_msg_thread = None
    try:
        final_status_from_engine = run_scan_process(
            job_id, job_path, targets, selected_tools_config,
            advanced_options, db_path, tool_definitions, app_logger_for_thread
        )
    except Exception as e:
        app_logger_for_thread.error(f"Excepción no controlada en el hilo del job {job_id}: {e}", exc_info=True)
        final_status_from_engine = "ERROR"
        error_msg_thread = str(e)
    finally:
        active_scan_threads.pop(job_id, None) # Eliminar de hilos activos
        try:
            with sqlite3.connect(db_path) as conn_final:
                final_db_update_params = [final_status_from_engine, datetime.datetime.now().isoformat()]
                final_db_update_query = "UPDATE job SET status = ?, end_timestamp = ?, overall_progress = 100"

                if error_msg_thread:
                    final_db_update_query += ", error_message = ?"
                    final_db_update_params.append(error_msg_thread)
                
                final_db_update_query += " WHERE id = ?"
                final_db_update_params.append(job_id)
                
                conn_final.execute(final_db_update_query, tuple(final_db_update_params))
                conn_final.commit()
                app_logger_for_thread.info(f"Job {job_id} finalizado en DB con estado: {final_status_from_engine}")

                if final_status_from_engine in ["COMPLETED", "COMPLETED_WITH_ERRORS", "CANCELLED"]:
                    if not Path(job_path).is_dir():
                        app_logger_for_thread.error(f"Error al crear ZIP para job {job_id}: El directorio del job '{job_path}' no existe.")
                        return

                    zip_filename_base = f"{job_id}_results"
                    archive_base_name_path = Path(app.config["RESULTS_DIR"]) / zip_filename_base # e.g. scan_results/scan_xxxx_results
                    archive_root_dir_path = Path(job_path).parent # e.g. scan_results
                    archive_item_name = Path(job_path).name # e.g. scan_xxxx

                    try:
                        shutil.make_archive(
                            str(archive_base_name_path), # path al archivo zip (sin .zip)
                            "zip",
                            root_dir=str(archive_root_dir_path),
                            base_dir=archive_item_name
                        )
                        zip_url_path_for_db = f"/api/results/download/{zip_filename_base}.zip" # Asumiendo que SCRIPT_ROOT es manejado por el cliente o es ""

                        conn_final.execute(
                            "UPDATE job SET zip_path = ? WHERE id = ?",
                            (zip_url_path_for_db, job_id),
                        )
                        conn_final.commit()
                        app_logger_for_thread.info(f"Resultados para job {job_id} empaquetados en {archive_base_name_path}.zip")
                    except Exception as e_zip:
                        app_logger_for_thread.error(f"Error al crear ZIP para job {job_id}: {e_zip}", exc_info=True)
                        summary_path_zip_err = Path(job_path) / "summary.json"
                        s_data_zip_err = helpers.get_scan_status_from_file(str(summary_path_zip_err))
                        s_data_zip_err["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Error creando ZIP: {e_zip}",
                            "level": "error", "is_html": False
                        })
                        helpers.save_job_summary(job_path, s_data_zip_err)
        except Exception as e_db_final:
            app_logger_for_thread.error(f"Error CRÍTICO al actualizar estado final en DB para job {job_id}: {e_db_final}", exc_info=True)


@app.route("/api/scan/start", methods=["POST"])
@login_required
def start_scan_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body debe ser JSON."}), 400

    targets_input = data.get("targets")
    selected_tools_payload = data.get("tools") # Espera [{id: "tool_id", cli_params: {}}, ...]
    advanced_options_input = data.get("advanced_options", {})

    if not targets_input or not isinstance(targets_input, list) or not all(isinstance(t, str) for t in targets_input):
        return jsonify({"error": "Faltan objetivos o el formato es incorrecto (se espera una lista de strings)."}), 400
    
    targets = [t.strip() for t in targets_input if t.strip()]
    if not targets:
        return jsonify({"error": "No se proporcionaron objetivos válidos."}), 400

    if not selected_tools_payload or not isinstance(selected_tools_payload, list):
        return jsonify({"error": "Faltan herramientas seleccionadas o el formato es incorrecto."}), 400

    job_id = f"scan_{helpers.get_current_timestamp_str()}"
    job_path = helpers.create_job_directories(base_path=app.config["RESULTS_DIR"], job_id=job_id)

    initial_summary_data = {
        "job_id": job_id, "user_id": current_user.id, "status": "PENDING",
        "targets": targets, "selected_tools_config": selected_tools_payload,
        "advanced_options": advanced_options_input,
        "creation_timestamp": datetime.datetime.now().isoformat(),
        "start_timestamp": None, "end_timestamp": None, "overall_progress": 0,
        "results_path": str(job_path), "zip_path": None, "error_message": None,
        "logs": [{"timestamp": datetime.datetime.now().isoformat(), "message": f"Job {job_id} creado y en cola.", "level": "info", "is_html": False}],
        "tool_progress": {},
    }
    
    tool_definitions_map = helpers.get_tools_definition()
    for target_val in targets:
        for tool_entry in selected_tools_payload:
            tool_id_for_prog = tool_entry['id']
            tool_name_for_prog = tool_definitions_map.get(tool_id_for_prog, {}).get('name', tool_id_for_prog)
            tool_prog_key = f"{tool_id_for_prog}_on_{target_val}"
            initial_summary_data["tool_progress"][tool_prog_key] = {
                "name": tool_name_for_prog, "status": "pending", "command": None, 
                "output_file": None, "start_time": None, "end_time": None, "error_message": None,
            }
    helpers.save_job_summary(job_path, initial_summary_data)

    db = get_db()
    try:
        db.execute(
            """INSERT INTO job (id, user_id, status, targets, selected_tools_config, advanced_options, creation_timestamp, results_path, overall_progress)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, current_user.id, "PENDING", json.dumps(targets), 
             json.dumps(selected_tools_payload), json.dumps(advanced_options_input), 
             initial_summary_data["creation_timestamp"], str(job_path), 0),
        )
        db.commit()
    except sqlite3.Error as e:
        app.logger.error(f"Error de DB al crear job {job_id}: {e}", exc_info=True)
        error_summary = helpers.get_scan_status_from_file(job_path)
        error_summary["status"] = "ERROR"
        error_summary["error_message"] = f"DB error: {e}"
        error_summary["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"DB error al crear job: {e}", "level": "error", "is_html": False})
        helpers.save_job_summary(job_path, error_summary)
        return jsonify({"error": f"Error de base de datos al crear el trabajo: {e}"}), 500

    tool_definitions_for_thread = helpers.get_tools_definition()
    thread_logger_instance = app.logger # Usar el logger de la app Flask

    scan_thread = threading.Thread(
        target=scan_job_thread_target,
        args=(job_id, job_path, targets, selected_tools_payload, advanced_options_input, 
              app.config["DATABASE"], tool_definitions_for_thread, thread_logger_instance),
    )
    active_scan_threads[job_id] = scan_thread
    scan_thread.start()

    try: # Actualizar estado a INITIALIZING después de iniciar el hilo
        db.execute("UPDATE job SET status = ? WHERE id = ?", ("INITIALIZING", job_id))
        db.commit()
        init_summary = helpers.get_scan_status_from_file(job_path)
        init_summary["status"] = "INITIALIZING"
        init_summary["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Job {job_id} ha comenzado la inicialización.", "level": "info", "is_html": False})
        helpers.save_job_summary(job_path, init_summary)
    except sqlite3.Error as e_update:
        app.logger.error(f"Error de DB al actualizar job {job_id} a INITIALIZING: {e_update}", exc_info=True)

    return jsonify({"message": "Trabajo de escaneo iniciado.", "job_id": job_id}), 202


@app.route("/api/scan/status/<job_id>", methods=["GET"])
@login_required
def scan_status_route(job_id):
    db = get_db()
    is_admin = current_user.id == 1 # Asumiendo que el ID 1 es admin
    
    query = "SELECT * FROM job WHERE id = ?"
    params = [job_id]
    if not is_admin:
        query += " AND user_id = ?"
        params.append(current_user.id)
        
    cur = db.execute(query, tuple(params))
    job_data_db = cur.fetchone()

    if not job_data_db:
        return jsonify({"error": "Job no encontrado o no autorizado."}), 404

    summary_data_from_file = helpers.get_scan_status_from_file(job_data_db["results_path"])

    response_data = {
        "job_id": job_data_db["id"],
        "status": job_data_db["status"], # Estado de la DB es la fuente de verdad para el estado general
        "overall_progress": job_data_db["overall_progress"],
        "start_time": job_data_db["start_timestamp"] or summary_data_from_file.get("start_timestamp"),
        "end_time": job_data_db["end_timestamp"],
        "targets": json.loads(job_data_db["targets"]) if job_data_db["targets"] else summary_data_from_file.get("targets", []),
        "logs": summary_data_from_file.get("logs", []),
        "tool_progress": summary_data_from_file.get("tool_progress", {}),
        "error_message": job_data_db["error_message"] or summary_data_from_file.get("error_message"),
        "zip_path": job_data_db["zip_path"], # zip_path siempre desde la DB
    }
    return jsonify(response_data)


@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    db = get_db()
    is_admin = current_user.id == 1
    query = "SELECT id, status, creation_timestamp, start_timestamp, targets, zip_path FROM job"
    params = []
    if not is_admin:
        query += " WHERE user_id = ?"
        params.append(current_user.id)
    query += " ORDER BY creation_timestamp DESC"
        
    cur = db.execute(query, tuple(params))
    jobs_raw = cur.fetchall()

    jobs_list = []
    for row in jobs_raw:
        jobs_list.append({
            "id": row["id"],
            "status": row["status"],
            "timestamp": row["start_timestamp"] or row["creation_timestamp"], # Preferir start_timestamp
            "targets": json.loads(row["targets"]) if row["targets"] else [],
            "zip_path": row["zip_path"],
        })
    return jsonify(jobs_list)


@app.route("/api/scan/cancel/<job_id>", methods=["POST"])
@login_required
def cancel_scan_route(job_id):
    db = get_db()
    is_admin = current_user.id == 1
    query = "SELECT status, results_path FROM job WHERE id = ?"
    params = [job_id]
    if not is_admin:
        query += " AND user_id = ?"
        params.append(current_user.id)

    cur = db.execute(query, tuple(params))
    job_data = cur.fetchone()

    if not job_data:
        return jsonify({"error": "Job no encontrado o no autorizado."}), 404

    current_status_db = job_data["status"]
    job_path = job_data["results_path"]

    if current_status_db not in ["PENDING", "INITIALIZING", "RUNNING"]:
        return jsonify({"message": f"Job {job_id} no está en un estado cancelable (actual: {current_status_db})."}), 400

    try:
        db.execute("UPDATE job SET status = ? WHERE id = ?", ("REQUEST_CANCEL", job_id))
        db.commit()

        summary_update_cancel = helpers.get_scan_status_from_file(job_path)
        summary_update_cancel["status"] = "REQUEST_CANCEL"
        summary_update_cancel.setdefault("logs", []).append({
            "timestamp": datetime.datetime.now().isoformat(),
            "message": f"Solicitud de cancelación recibida para job {job_id}.",
            "level": "warn", "is_html": False
        })
        helpers.save_job_summary(job_path, summary_update_cancel)
        app.logger.info(f"Solicitud de cancelación para job {job_id} registrada.")
        return jsonify({"message": f"Solicitud de cancelación para el job {job_id} enviada."}), 200
    except sqlite3.Error as e_db:
        app.logger.error(f"Error de DB al cancelar job {job_id}: {e_db}", exc_info=True)
        return jsonify({"error": "Error de base de datos al solicitar cancelación."}), 500
    except Exception as e_file: # Error al actualizar summary
        app.logger.error(f"Error de archivo al actualizar summary para cancelación de job {job_id}: {e_file}", exc_info=True)
        return jsonify({"message": f"Solicitud de cancelación para el job {job_id} enviada (error al actualizar summary)."}), 200


@app.route("/api/results/download/<path:zip_filename>")
@login_required
def download_job_results_zip(zip_filename):
    if ".." in zip_filename or zip_filename.startswith("/"): # Simple validación
        return jsonify({"error": "Nombre de archivo inválido."}), 400

    db = get_db()
    
    is_admin = current_user.id == 1
    query = "SELECT results_path FROM job WHERE zip_path LIKE ? ESCAPE '!'" # Usar LIKE para flexibilidad con SCRIPT_ROOT
    like_pattern = f"%/{zip_filename}" 
    params = [like_pattern]

    if not is_admin:
        query += " AND user_id = ?"
        params.append(current_user.id)
    
    cur = db.execute(query, tuple(params))
    job_data = cur.fetchone()

    if not job_data:
        app.logger.warning(f"Intento de descarga de ZIP no autorizado o no encontrado: {zip_filename} para user {current_user.id}")
        return jsonify({"error": "Archivo ZIP no encontrado o no autorizado."}), 404
    
    file_on_disk_path = Path(app.config["RESULTS_DIR"]) / zip_filename

    if not file_on_disk_path.is_file():
        app.logger.error(f"Archivo ZIP {file_on_disk_path} no encontrado en disco (DB like pattern: {like_pattern}).")
        return jsonify({"error": "Archivo ZIP no encontrado en el servidor."}), 404

    try:
        return send_file(
            str(file_on_disk_path),
            as_attachment=True,
            download_name=zip_filename, # El nombre que verá el usuario al descargar
            mimetype="application/zip",
        )
    except Exception as e:
        app.logger.error(f"Error al enviar archivo ZIP {zip_filename}: {e}", exc_info=True)
        return jsonify({"error": "No se pudo enviar el archivo ZIP."}), 500


if __name__ == "__main__":
    with app.app_context(): # Asegura que app.logger y otras extensiones estén disponibles
        if not Path(app.config["DATABASE"]).exists():
            app.logger.info(f"Base de datos no encontrada en {app.config['DATABASE']}. Inicializando...")
            init_db_command()
        else:
            conn_check = sqlite3.connect(app.config["DATABASE"])
            try:
                conn_check.execute("SELECT COUNT(*) FROM job").fetchone()
                conn_check.execute("SELECT COUNT(*) FROM user").fetchone()
            except sqlite3.OperationalError:
                 app.logger.warning(f"Una o más tablas no existen en {app.config['DATABASE']}. Reinicializando...")
                 init_db_command() # Reinicializar si las tablas no existen
            finally:
                conn_check.close()


    env_mode = os.environ.get("APP_ENV_MODE", "PROD").upper()
    run_host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    try:
        run_port = int(os.environ.get("FLASK_RUN_PORT", 5000))
    except ValueError:
        run_port = 5000
        app.logger.warning("FLASK_RUN_PORT inválido, usando puerto 5000 por defecto.")

    flask_debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]

    if env_mode == "DEBUG":
        run_port = int(os.environ.get("FLASK_RUN_PORT", 5001)) # Puerto diferente para DEBUG si no se especifica
        run_host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
        flask_debug_mode = True # Forzar debug en modo DEBUG
        app.logger.setLevel(logging.DEBUG) # Más logs en modo debug
        app.logger.info(f"MODO DEBUG activado. Escuchando en http://{run_host}:{run_port}")
    elif env_mode == "DEMO":
        run_port = int(os.environ.get("FLASK_RUN_PORT", 5002))
        run_host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
        app.logger.info(f"MODO DEMO activado. Escuchando en http://{run_host}:{run_port}. Debug: {flask_debug_mode}")
    elif env_mode == "PROD":
        app.logger.info(f"MODO PRODUCCIÓN activado. Escuchando en http://{run_host}:{run_port}. Debug: {flask_debug_mode}")
    else:
        app.logger.warning(f"APP_ENV_MODE '{env_mode}' no reconocido. Usando configuración de PRODUCCIÓN por defecto (http://{run_host}:{run_port}). Debug: {flask_debug_mode}")

    if flask_debug_mode:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO) # Nivel INFO para producción

    app.run(host=run_host, port=run_port, debug=flask_debug_mode)