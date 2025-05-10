from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_file,
    current_app,
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
import re  # For cleaning up command templates
import subprocess # Asegurándonos que está importado para run_scan_process

from utils import helpers


# Placeholder for the scan engine logic
# In a real application, this would be in a separate module (e.g., scanner/engine.py)
# and would contain the actual tool execution logic.
def run_scan_process(
    job_id,
    job_path,
    targets,
    selected_tools_config_list,
    advanced_options,
    db_path_for_thread,
    tool_definitions_for_thread,
    app_logger,
):
    app_logger.info(f"Motor de escaneo iniciado para job {job_id} en {job_path}")

    # Ensure tool_outputs directory exists
    tool_outputs_dir = Path(job_path) / "tool_outputs"
    os.makedirs(tool_outputs_dir, exist_ok=True)

    job_summary_path = Path(job_path) / "summary.json"

    # Initial summary data structure (will be updated by the main thread before this starts)
    current_summary_data = {}
    if job_summary_path.exists():
        try:
            with open(job_summary_path, "r", encoding="utf-8") as f_sum:
                current_summary_data = json.load(f_sum)
        except json.JSONDecodeError:
            app_logger.error(
                f"Job {job_id}: summary.json corrupt at start of scan process."
            )
            current_summary_data = {"logs": [], "tool_progress": {}}  # Fallback

    if "logs" not in current_summary_data:
        current_summary_data["logs"] = []
    if "tool_progress" not in current_summary_data:
        current_summary_data["tool_progress"] = {}

    total_tools_to_run = len(targets) * len(selected_tools_config_list)
    completed_tools_count = 0

    conn_thread = sqlite3.connect(db_path_for_thread)
    conn_thread.row_factory = sqlite3.Row

    try:
        for target_idx, target_item in enumerate(targets):
            # Target can be a simple string or an object if more details are needed
            target_value = (
                target_item
                if isinstance(target_item, str)
                else target_item.get("value", str(target_item))
            )

            for tool_config_entry in selected_tools_config_list:
                tool_id = tool_config_entry["id"]
                user_cli_params_for_tool = tool_config_entry.get(
                    "cli_params", {}
                )  # Params specific to this tool invocation
                tool_definition = tool_definitions_for_thread.get(tool_id, {})

                # Check for cancellation request
                cursor_cancel = conn_thread.cursor()
                cursor_cancel.execute("SELECT status FROM job WHERE id = ?", (job_id,))
                job_status_db = cursor_cancel.fetchone()
                cursor_cancel.close()
                if job_status_db and job_status_db["status"] in [
                    "REQUEST_CANCEL",
                    "CANCELLED",
                ]:
                    app_logger.info(
                        f"Cancelación detectada para job {job_id} dentro del motor. Herramienta {tool_id} en {target_value} no se ejecutará."
                    )
                    current_summary_data["logs"].append(
                        {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Escaneo cancelado antes de ejecutar {tool_id} en {target_value}.",
                            "type": "warn",
                        }
                    )
                    with open(job_summary_path, "w", encoding="utf-8") as f_sum:
                        json.dump(current_summary_data, f_sum, indent=4)
                    conn_thread.close()
                    return "CANCELLED"

                tool_output_filename = f"{tool_id}_{target_value.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}.txt"
                tool_output_filepath = tool_outputs_dir / tool_output_filename

                command_template = tool_definition.get("command_template", "")
                if not command_template:
                    app_logger.warning(
                        f"Job {job_id}: No command template for tool {tool_id}"
                    )
                    current_summary_data["logs"].append(
                        {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"No se encontró plantilla de comando para {tool_id}.",
                            "type": "error",
                        }
                    )
                    current_summary_data["tool_progress"][
                        f"{tool_id}_on_{target_value}"
                    ] = {
                        "status": "error",
                        "error_message": "No command template",
                        "output_file": None,
                    }
                    continue

                # Replace placeholders
                final_command = command_template
                final_command = final_command.replace("{target}", target_value)
                final_command = final_command.replace(
                    "{target_url}", target_value
                )  # Common placeholder
                final_command = final_command.replace(
                    "{target_host_or_ip}", target_value
                )  # Common placeholder
                final_command = final_command.replace("{target_domain}", target_value)
                final_command = final_command.replace(
                    "{output_file}", str(tool_output_filepath)
                )
                final_command = final_command.replace(
                    "{output_file_base}",
                    str(
                        tool_outputs_dir
                        / f"{tool_id}_{target_value.replace('://', '_').replace('/', '_').replace(':', '_')}"
                    ),
                )
                final_command = final_command.replace(
                    "{output_file_json}", str(tool_output_filepath.with_suffix(".json"))
                )
                final_command = final_command.replace(
                    "{output_file_xml}", str(tool_output_filepath.with_suffix(".xml"))
                )
                final_command = final_command.replace(
                    "{output_file_dir}", str(tool_outputs_dir)
                )

                # Replace tool-specific CLI parameters from user_cli_params_for_tool and advanced_options
                # Priority: user_cli_params_for_tool > advanced_options (tool specific) > advanced_options (global)

                # Global advanced options might influence parameters too (e.g., Nmap timing)
                if tool_id == "nmap_top_ports" and advanced_options.get(
                    "customScanTime"
                ):
                    final_command = final_command.replace(
                        "{nmap_timing_option}", advanced_options["customScanTime"]
                    )
                else:  # remove placeholder if not set
                    final_command = final_command.replace(
                        "{nmap_timing_option}",
                        tool_definition.get("cli_params_config", [{}])[0].get(
                            "default", "-T3"
                        ),
                    )

                for param_key, param_value in user_cli_params_for_tool.items():
                    final_command = final_command.replace(
                        f"{{{param_key}}}", str(param_value)
                    )

                # Remove any remaining unreplaced placeholders like {some_other_param}
                final_command = re.sub(r"\{[a-zA-Z0-9_]+\}", "", final_command)
                # Ensure multiple spaces are condensed to one, but not if they are quoted
                final_command = ' '.join(final_command.split())


                app_logger.info(
                    f"Job {job_id}: Ejecutando [{tool_id}] en [{target_value}]: {final_command}"
                )
                current_summary_data["logs"].append(
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Ejecutando: {final_command}",
                        "type": "command",
                    }
                )
                current_summary_data["tool_progress"][
                    f"{tool_id}_on_{target_value}"
                ] = {
                    "status": "running",
                    "command": final_command,
                    "start_time": datetime.datetime.now().isoformat(),
                }
                with open(job_summary_path, "w", encoding="utf-8") as f_sum:
                    json.dump(current_summary_data, f_sum, indent=4)

                tool_run_status = "error"  # Default to error
                tool_error_message = ""
                try:
                    # Actual tool execution
                    process = subprocess.run(
                        final_command,
                        shell=tool_definition.get(
                            "needs_shell", False
                        ),  # Critical for security
                        capture_output=True,
                        text=True,
                        timeout=int(
                            advanced_options.get("tool_timeout", 3600)
                        ),  # Default 1 hour timeout per tool
                        check=False,  # Don't raise exception for non-zero exit codes immediately
                    )
                    with open(tool_output_filepath, "w", encoding="utf-8") as f_out:
                        f_out.write(f"--- Command ---\n{final_command}\n\n")
                        f_out.write(
                            f"--- STDOUT for {tool_definition.get('name', tool_id)} on {target_value} ---\n"
                        )
                        f_out.write(process.stdout if process.stdout else "")
                        f_out.write(
                            f"\n\n--- STDERR for {tool_definition.get('name', tool_id)} on {target_value} ---\n"
                        )
                        f_out.write(process.stderr if process.stderr else "")

                    if process.returncode == 0:
                        tool_run_status = "completed"
                        current_summary_data["logs"].append(
                            {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "message": f"{tool_id} en {target_value} completado.",
                                "type": "success",
                            }
                        )
                    else:
                        tool_run_status = "error"
                        tool_error_message = f"Exit code {process.returncode}. Stderr: {process.stderr[:200]}"
                        current_summary_data["logs"].append(
                            {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "message": f"Error en {tool_id} en {target_value}: {tool_error_message}",
                                "type": "error",
                            }
                        )

                except subprocess.TimeoutExpired:
                    tool_run_status = "error"
                    tool_error_message = "Timeout Expirado"
                    current_summary_data["logs"].append(
                        {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Timeout para {tool_id} en {target_value}.",
                            "type": "error",
                        }
                    )
                    with open(tool_output_filepath, "a", encoding="utf-8") as f_out:
                        f_out.write("\n\n--- ERROR: TIMEOUT EXPIRED ---")
                except Exception as e_tool:
                    tool_run_status = "error"
                    tool_error_message = str(e_tool)
                    app_logger.error( # Usar el logger pasado
                        f"Job {job_id}: Excepción ejecutando {tool_id} en {target_value}: {e_tool}"
                    )
                    current_summary_data["logs"].append(
                        {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Excepción en {tool_id} en {target_value}: {e_tool}",
                            "type": "error",
                        }
                    )
                    with open(tool_output_filepath, "a", encoding="utf-8") as f_out:
                        f_out.write(f"\n\n--- EXCEPTION: {e_tool} ---")

                completed_tools_count += 1
                current_progress = (
                    int((completed_tools_count / total_tools_to_run) * 100)
                    if total_tools_to_run > 0
                    else 0
                )

                current_summary_data["tool_progress"][
                    f"{tool_id}_on_{target_value}"
                ].update(
                    {
                        "status": tool_run_status,
                        "output_file": str(
                            tool_output_filepath.name
                        ),  # Store relative path or just name
                        "end_time": datetime.datetime.now().isoformat(),
                        "error_message": (
                            tool_error_message if tool_error_message else None
                        ),
                    }
                )
                current_summary_data["overall_progress"] = current_progress
                with open(job_summary_path, "w", encoding="utf-8") as f_sum:
                    json.dump(current_summary_data, f_sum, indent=4)

                conn_thread.execute(
                    "UPDATE job SET overall_progress = ? WHERE id = ?",
                    (current_progress, job_id),
                )
                conn_thread.commit()

        final_job_status = "COMPLETED"
        if any(
            tp.get("status") == "error"
            for tp in current_summary_data["tool_progress"].values()
        ):
            final_job_status = "COMPLETED_WITH_ERRORS"

        # Check final cancellation status from DB one last time
        cursor_final_cancel = conn_thread.cursor()
        cursor_final_cancel.execute("SELECT status FROM job WHERE id = ?", (job_id,))
        job_final_status_db = cursor_final_cancel.fetchone()
        cursor_final_cancel.close()
        if job_final_status_db and job_final_status_db["status"] == "CANCELLED":
            final_job_status = (
                "CANCELLED"  # Override if it was cancelled during the last tool run
            )

    except Exception as e_main:
        app_logger.error( # Usar el logger pasado
            f"Error mayor en el motor de escaneo para job {job_id}: {e_main}"
        )
        current_summary_data["logs"].append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Error crítico del motor: {e_main}",
                "type": "error",
            }
        )
        current_summary_data["error_message"] = str(e_main)
        with open(job_summary_path, "w", encoding="utf-8") as f_sum:
            json.dump(current_summary_data, f_sum, indent=4)
        final_job_status = "ERROR"
    finally:
        conn_thread.close()

    return final_job_status


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.config["DATABASE"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "panthera.db"
)
app.config["RESULTS_DIR"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scan_results"
)
app.config["TOOLS_CONFIG_PATH"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tools_config.json"
)
app.config["MAX_PARALLEL_THREADS_PER_JOB"] = int(
    os.environ.get("MAX_PARALLEL_THREADS_PER_JOB", 1)
)  # Limita hilos por job

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

active_scan_threads = {}  # job_id: threading.Thread object


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
    app.logger.info("Base de datos inicializada.") # Usar app.logger
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE username = ?", ("panthera",))
    if cursor.fetchone() is None:
        hashed_password = generate_password_hash("panthera", method="pbkdf2:sha256")
        cursor.execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("panthera", hashed_password),
        )
        db.commit()
        app.logger.info("Usuario por defecto 'panthera' creado.") # Usar app.logger


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
helpers.CONFIG_FILE_PATH = app.config["TOOLS_CONFIG_PATH"]


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
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("scans.html")


@app.route("/api/config", methods=["GET"])
@login_required
def get_app_config_route():
    try:
        config_data = {
            "tools": helpers.get_tools_definition(),
            "profiles": helpers.get_scan_profiles(),
            "phases": helpers.get_pentest_phases(),
            "script_root": request.script_root,
        }
        return jsonify(config_data)
    except Exception as e:
        app.logger.error(f"Error al cargar configuración: {e}") # Usar app.logger
        return (
            jsonify({"error": "No se pudo cargar la configuración del servidor."}),
            500,
        )


def scan_job_thread_target(
    job_id,
    job_path,
    targets,
    selected_tools_config,
    advanced_options,
    db_path,
    tool_definitions,
    app_logger_for_thread,
):
    """Wrapper to call the scan process and update DB on completion/error."""
    final_status = "ERROR"  # Default in case of unexpected crash in run_scan_process
    error_msg_thread = None
    try:
        # Pass the logger to the scan process
        final_status = run_scan_process(
            job_id,
            job_path,
            targets,
            selected_tools_config,
            advanced_options,
            db_path,
            tool_definitions,
            app_logger_for_thread,
        )
    except Exception as e:
        app_logger_for_thread.error(
            f"Excepción no controlada en el hilo del job {job_id}: {e}"
        )
        final_status = "ERROR"
        error_msg_thread = str(e)
    finally:
        active_scan_threads.pop(job_id, None)
        try:
            with sqlite3.connect(db_path) as conn_final:
                # Ensure end_timestamp is set, and status reflects outcome
                final_update_query = "UPDATE job SET status = ?, end_timestamp = ?, overall_progress = 100"
                params = [final_status, datetime.datetime.now().isoformat()]
                if error_msg_thread:
                    final_update_query += ", error_message = ?"
                    params.append(error_msg_thread)
                final_update_query += " WHERE id = ?"
                params.append(job_id)

                conn_final.execute(final_update_query, tuple(params))
                conn_final.commit()
                app_logger_for_thread.info(
                    f"Job {job_id} finalizado en DB con estado: {final_status}"
                )

                # Attempt to create ZIP archive if completed successfully or with errors
                if final_status in ["COMPLETED", "COMPLETED_WITH_ERRORS"]:
                    zip_filename_base = f"{job_id}_results"
                    # Corregir para que el zip se guarde en RESULTS_DIR directamente, no en un subdirectorio de job_path
                    zip_path_on_disk = Path(app.config["RESULTS_DIR"]) / f"{zip_filename_base}.zip"
                    archive_root_dir = Path(job_path).parent # El directorio que contiene la carpeta del job (ej. scan_results)
                    archive_base_name = Path(app.config["RESULTS_DIR"]) / zip_filename_base # Nombre base para el archivo sin extensión
                    
                    try:
                        shutil.make_archive(
                            str(archive_base_name), # path sin .zip
                            "zip",      # formato
                            root_dir=archive_root_dir, # Directorio desde el cual archivar
                            base_dir=Path(job_path).name # Directorio a archivar, relativo a root_dir
                        )
                        zip_url_path = f"/api/results/download/{zip_filename_base}.zip"
                        conn_final.execute(
                            "UPDATE job SET zip_path = ? WHERE id = ?",
                            (zip_url_path, job_id),
                        )
                        conn_final.commit()
                        app_logger_for_thread.info(
                            f"Resultados para job {job_id} empaquetados en {zip_path_on_disk}"
                        )
                    except Exception as e_zip:
                        app_logger_for_thread.error(
                            f"Error al crear ZIP para job {job_id}: {e_zip}"
                        )
                        # Log this error in summary.json as well
                        summary_path = Path(job_path) / "summary.json"
                        s_data = {}
                        if summary_path.exists():
                            try:
                                with open(summary_path, "r", encoding="utf-8") as f:
                                    s_data = json.load(f)
                            except json.JSONDecodeError: # Manejar corrupción de summary.json
                                s_data = {"logs": []} 
                        if "logs" not in s_data:
                            s_data["logs"] = []
                        s_data["logs"].append(
                            {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "message": f"Error creando ZIP: {e_zip}",
                                "type": "error",
                            }
                        )
                        with open(summary_path, "w", encoding="utf-8") as f:
                            json.dump(s_data, f, indent=4)

        except Exception as e_db_final:
            app_logger_for_thread.error(
                f"Error CRÍTICO al actualizar estado final en DB para job {job_id}: {e_db_final}"
            )


@app.route("/api/scan/start", methods=["POST"])
@login_required
def start_scan_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body debe ser JSON."}), 400

    targets_input = data.get("targets")
    selected_tools_payload = data.get(
        "tools"
    )  # Espera [{id: "tool_id", cli_params: {}}, ...]
    advanced_options_input = data.get("advanced_options", {})

    if (
        not targets_input
        or not isinstance(targets_input, list)
        or not all(isinstance(t, str) for t in targets_input)
    ):
        return (
            jsonify(
                {
                    "error": "Faltan objetivos o el formato es incorrecto (se espera una lista de strings)."
                }
            ),
            400,
        )

    targets = [t.strip() for t in targets_input if t.strip()]
    if not targets:
        return jsonify({"error": "No se proporcionaron objetivos válidos."}), 400

    if not selected_tools_payload or not isinstance(selected_tools_payload, list):
        return (
            jsonify(
                {
                    "error": "Faltan herramientas seleccionadas o el formato es incorrecto."
                }
            ),
            400,
        )

    job_id = f"scan_{helpers.get_current_timestamp_str()}"
    job_path, _ = helpers.create_job_directories(
        app.config["RESULTS_DIR"], job_id, targets # targets no se usa aquí, helpers lo usa internamente
    )


    initial_summary_data = {
        "job_id": job_id,
        "user_id": current_user.id,
        "status": "PENDING", # Estado inicial antes de que el hilo lo tome
        "targets": targets,
        "selected_tools_config": selected_tools_payload,
        "advanced_options": advanced_options_input,
        "creation_timestamp": datetime.datetime.now().isoformat(),
        "start_timestamp": None, # El hilo lo establecerá
        "end_timestamp": None,
        "overall_progress": 0,
        "results_path": str(job_path),  # Store as string
        "zip_path": None,
        "error_message": None,
        "logs": [
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Job {job_id} creado y en cola.",
                "type": "info",
            }
        ],
        "tool_progress": { # Inicializar progreso para cada herramienta/objetivo combinación
             # Esto se llenará dinámicamente por el motor de escaneo
        },
    }
    # Inicializar tool_progress con todas las herramientas planeadas
    for target_val in targets:
        for tool_entry in selected_tools_payload:
            tool_prog_key = f"{tool_entry['id']}_on_{target_val}"
            initial_summary_data["tool_progress"][tool_prog_key] = {
                "status": "pending",
                "command": None,
                "output_file": None,
                "start_time": None,
                "end_time": None,
                "error_message": None,
            }

    helpers.save_job_summary(
        job_path, initial_summary_data
    )  # Save initial summary.json

    db = get_db()
    try:
        # El estado inicial en DB es PENDING. El hilo lo cambiará a RUNNING.
        db.execute(
            """INSERT INTO job (id, user_id, status, targets, selected_tools_config, advanced_options, creation_timestamp, start_timestamp, results_path, overall_progress)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                current_user.id,
                "PENDING", # Estado inicial
                json.dumps(targets),
                json.dumps(selected_tools_payload),
                json.dumps(advanced_options_input),
                initial_summary_data["creation_timestamp"],
                datetime.datetime.now().isoformat(), # start_timestamp es cuando se encola, no cuando el hilo corre
                str(job_path),
                0,
            ),
        )
        db.commit()
    except sqlite3.Error as e:
        app.logger.error(f"Error de DB al crear job {job_id}: {e}") # Usar app.logger
        helpers.save_job_summary(
            job_path,
            {
                "status": "ERROR",
                "error_message": f"DB error: {e}",
                "logs": [
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"DB error al crear job: {e}",
                        "type": "error",
                    }
                ],
            },
        )
        return (
            jsonify({"error": f"Error de base de datos al crear el trabajo: {e}"}),
            500,
        )

    tool_definitions = helpers.get_tools_definition()  # Cargar una vez

    # Pasar una copia del logger de la app al hilo
    thread_logger = app.logger # Usar app.logger, no current_app.logger aquí

    scan_thread = threading.Thread(
        target=scan_job_thread_target,
        args=(
            job_id,
            job_path,
            targets,
            selected_tools_payload,
            advanced_options_input,
            app.config["DATABASE"],
            tool_definitions,
            thread_logger,
        ),
    )
    active_scan_threads[job_id] = scan_thread
    scan_thread.start()
    
    # Actualizar estado a INITIALIZING o RUNNING en DB y summary después de iniciar hilo
    try:
        db.execute("UPDATE job SET status = ?, start_timestamp = ? WHERE id = ?", 
                   ("INITIALIZING", datetime.datetime.now().isoformat(), job_id))
        db.commit()
        initial_summary_data["status"] = "INITIALIZING"
        initial_summary_data["start_timestamp"] = datetime.datetime.now().isoformat()
        initial_summary_data["logs"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "message": f"Job {job_id} ha comenzado la inicialización.",
            "type": "info",
        })
        helpers.save_job_summary(job_path, initial_summary_data)
    except sqlite3.Error as e_update:
        app.logger.error(f"Error de DB al actualizar job {job_id} a INITIALIZING: {e_update}")


    return jsonify({"message": "Trabajo de escaneo iniciado.", "job_id": job_id}), 202


@app.route("/api/scan/status/<job_id>", methods=["GET"])
@login_required
def scan_status_route(job_id):
    db = get_db()
    cur = db.execute(
        "SELECT * FROM job WHERE id = ? AND user_id = ?", (job_id, current_user.id)
    )
    job_data_db = cur.fetchone()

    if not job_data_db:
        return jsonify({"error": "Job no encontrado o no autorizado."}), 404

    # Cargar el summary.json para obtener logs y tool_progress detallado
    job_path = job_data_db["results_path"]
    summary_file_path = Path(job_path) / "summary.json"
    summary_data_file = {}
    if summary_file_path.exists():
        try:
            with open(summary_file_path, "r", encoding="utf-8") as f:
                summary_data_file = json.load(f)
        except json.JSONDecodeError:
            app.logger.warning( # Usar app.logger
                f"Job {job_id}: summary.json corrupto al obtener estado."
            )
            summary_data_file = {
                "logs": [{"message": "summary.json corrupto", "type": "error", "timestamp": datetime.datetime.now().isoformat()}],
                "tool_progress": {},
            }
    else: # Si summary.json no existe por alguna razón crítica
        summary_data_file = {
            "logs": [{"message": "summary.json no encontrado", "type": "error", "timestamp": datetime.datetime.now().isoformat()}],
            "tool_progress": {},
        }


    response_data = {
        "job_id": job_data_db["id"],
        "status": job_data_db["status"], # El estado de la DB es la fuente de verdad principal
        "overall_progress": job_data_db["overall_progress"],
        "start_time": job_data_db["start_timestamp"],
        "end_time": job_data_db["end_timestamp"],
        "targets": json.loads(job_data_db["targets"]) if job_data_db["targets"] else [],
        "logs": summary_data_file.get("logs", []),  # Logs desde summary.json
        "tool_progress": summary_data_file.get(
            "tool_progress", {}
        ),  # Progreso detallado desde summary.json
        "error_message": job_data_db["error_message"]
        or summary_data_file.get("error_message"),
        "zip_path": job_data_db["zip_path"],
    }
    return jsonify(response_data)


@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    db = get_db()
    cur = db.execute(
        "SELECT id, status, creation_timestamp, targets, zip_path FROM job WHERE user_id = ? ORDER BY creation_timestamp DESC",
        (current_user.id,),
    )
    jobs_raw = cur.fetchall()

    jobs_list = []
    for row in jobs_raw:
        jobs_list.append(
            {
                "id": row["id"],
                "status": row["status"],
                "timestamp": row[
                    "creation_timestamp"
                ],  # Usar creation_timestamp para consistencia
                "targets": json.loads(row["targets"]) if row["targets"] else [],
                "zip_path": row["zip_path"],
            }
        )
    return jsonify(jobs_list)


@app.route("/api/scan/cancel/<job_id>", methods=["POST"])
@login_required
def cancel_scan_route(job_id):
    db = get_db()
    cur = db.execute(
        "SELECT status, results_path FROM job WHERE id = ? AND user_id = ?",
        (job_id, current_user.id),
    )
    job_data = cur.fetchone()

    if not job_data:
        return jsonify({"error": "Job no encontrado o no autorizado."}), 404

    current_status = job_data["status"]
    job_path = job_data["results_path"]

    if current_status not in ["PENDING", "INITIALIZING", "RUNNING"]:
        return (
            jsonify(
                {
                    "message": f"Job {job_id} no está en un estado cancelable (estado actual: {current_status})."
                }
            ),
            400,
        )

    try:
        # Actualizar estado en DB a REQUEST_CANCEL. El hilo del job debería detectarlo.
        db.execute("UPDATE job SET status = ? WHERE id = ?", ("REQUEST_CANCEL", job_id))
        db.commit()

        # Actualizar summary.json también
        summary_file_path = Path(job_path) / "summary.json"
        s_data = {}
        if summary_file_path.exists():
            try:
                with open(summary_file_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
            except json.JSONDecodeError:
                 s_data = {"logs": []} # Manejar corrupción
        if "logs" not in s_data:
            s_data["logs"] = []
        s_data["status"] = "REQUEST_CANCEL" # Reflejar el estado de solicitud
        s_data["logs"].append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Solicitud de cancelación recibida para job {job_id}.",
                "type": "warn",
            }
        )
        with open(summary_file_path, "w", encoding="utf-8") as f:
            json.dump(s_data, f, indent=4)

        app.logger.info( # Usar app.logger
            f"Solicitud de cancelación para job {job_id} registrada."
        )
        return (
            jsonify(
                {"message": f"Solicitud de cancelación para el job {job_id} enviada."}
            ),
            200,
        )
    except sqlite3.Error as e:
        app.logger.error(f"Error de DB al cancelar job {job_id}: {e}") # Usar app.logger
        return (
            jsonify({"error": "Error de base de datos al solicitar cancelación."}),
            500,
        )


@app.route(
    "/api/results/download/<zip_filename>"
)  # Cambiado para usar el nombre del archivo directamente
@login_required
def download_job_results_zip(zip_filename):
    db = get_db()
    db_zip_path_search = f"/api/results/download/{zip_filename}"
    cur = db.execute(
        "SELECT results_path FROM job WHERE zip_path = ? AND user_id = ?", # Buscar por el zip_path completo
        (db_zip_path_search, current_user.id),
    )
    job_data = cur.fetchone()

    if not job_data:
        # Intentar buscar por job ID si el zip_filename es solo el ID del job (menos seguro, pero como fallback)
        # Esto asume que zip_filename podría ser job_id + "_results.zip"
        if zip_filename.endswith("_results.zip"):
            possible_job_id = zip_filename.replace("_results.zip", "")
            cur_fallback = db.execute(
                 "SELECT results_path, zip_path FROM job WHERE id = ? AND user_id = ?", (possible_job_id, current_user.id)
            )
            job_data_fallback = cur_fallback.fetchone()
            if job_data_fallback and job_data_fallback["zip_path"] == db_zip_path_search:
                job_data = job_data_fallback # Usar este si coincide
            else:
                 return jsonify({"error": "Archivo ZIP no encontrado o no autorizado (búsqueda fallback fallida)."}), 404
        else:
            return jsonify({"error": "Archivo ZIP no encontrado o no autorizado."}), 404


    file_on_disk_path = Path(app.config["RESULTS_DIR"]) / zip_filename

    if not file_on_disk_path.is_file():
        app.logger.error( # Usar app.logger
            f"Archivo ZIP {file_on_disk_path} no encontrado en disco para job (DB path: {db_zip_path_search})."
        )
        return jsonify({"error": "Archivo ZIP no encontrado en el servidor."}), 404

    try:
        return send_file(
            str(file_on_disk_path),
            as_attachment=True,
            download_name=zip_filename, # El nombre que verá el usuario al descargar
            mimetype="application/zip",
        )
    except Exception as e:
        app.logger.error(f"Error al enviar archivo ZIP {zip_filename}: {e}") # Usar app.logger
        return jsonify({"error": "No se pudo enviar el archivo ZIP."}), 500


if __name__ == "__main__":
    # Crear la base de datos y el usuario por defecto si no existen al iniciar
    with app.app_context(): # Asegura que app.logger y otras extensiones estén disponibles
        if not Path(app.config["DATABASE"]).exists():
            app.logger.info(
                f"Base de datos no encontrada en {app.config['DATABASE']}. Inicializando..."
            )
            init_db_command()
        else:
            # Verificar si la tabla 'job' existe, si no, podría ser una DB antigua
            conn = get_db()
            cursor_check = conn.cursor()
            cursor_check.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='job';"
            )
            if not cursor_check.fetchone():
                app.logger.warning(
                    "La tabla 'job' no existe. Es posible que necesites reinicializar la DB con 'flask init-db'."
                )
            cursor_check.close()

    # --- MODIFICACIÓN PARA PUERTOS DINÁMICOS ---
    env_mode = os.environ.get("APP_ENV_MODE", "PROD").upper()
    run_host = "0.0.0.0"  # Por defecto para PROD y si se quiere acceso de red local
    run_port = 5000       # Puerto por defecto para PROD
    flask_debug_mode = False # Por defecto, debug desactivado

    if env_mode == "DEBUG":
        run_port = 5001       # Puerto para modo DEBUG
        run_host = "127.0.0.1" # Escuchar solo en localhost para DEBUG (acceso vía Tor local)
        flask_debug_mode = True
        # app.logger está disponible aquí porque estamos fuera del app_context() del if __name__
        # pero la instancia 'app' ya existe. Flask configura su logger al crear la instancia.
        app.logger.info(f"MODO DEBUG activado. Escuchando en http://{run_host}:{run_port}")
    elif env_mode == "DEMO":
        run_port = 5002       # Puerto para modo DEMO
        run_host = "127.0.0.1" # Escuchar solo en localhost para DEMO (acceso vía Tor local)
        flask_debug_mode = False # O True si se desea modo debug en DEMO
        app.logger.info(f"MODO DEMO activado. Escuchando en http://{run_host}:{run_port}")
    elif env_mode == "PROD":
        # flask_debug_mode ya es False
        app.logger.info(f"MODO PRODUCCIÓN activado. Escuchando en http://{run_host}:{run_port}")
    else:
        app.logger.warning(
            f"APP_ENV_MODE '{env_mode}' no reconocido. Usando configuración de PRODUCCIÓN por defecto (http://{run_host}:{run_port})."
        )
        # Se mantiene la configuración de PROD por defecto (puerto 5000, debug False)

    # --- FIN DE MODIFICACIÓN ---

    app.run(host=run_host, port=run_port, debug=flask_debug_mode)