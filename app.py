import logging
import click
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_file,
    redirect,
    url_for,
    flash
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
import json
import threading
import shutil
from pathlib import Path
import time
import re
import subprocess
import shlex

from utils import helpers

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
INSTANCE_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
os.makedirs(INSTANCE_FOLDER_PATH, exist_ok=True)

DB_NAME = "panthera_app.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(INSTANCE_FOLDER_PATH, DB_NAME)}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["RESULTS_DIR"] = os.path.join(INSTANCE_FOLDER_PATH, "scan_results")
os.makedirs(app.config["RESULTS_DIR"], exist_ok=True)
app.config["MAX_PARALLEL_THREADS_PER_JOB"] = int(os.environ.get("MAX_PARALLEL_THREADS_PER_JOB", 1))

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

active_scan_threads = {}

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    jobs = db.relationship('Job', backref='user_ref', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Job(db.Model):
    __tablename__ = 'job'
    id = db.Column(db.String(80), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=False)
    targets = db.Column(db.Text)
    selected_tools_config = db.Column(db.Text)
    advanced_options = db.Column(db.Text)
    creation_timestamp = db.Column(db.String(50), nullable=False)
    start_timestamp = db.Column(db.String(50))
    end_timestamp = db.Column(db.String(50))
    overall_progress = db.Column(db.Integer, default=0)
    results_path = db.Column(db.String(255))
    zip_path = db.Column(db.String(255))
    error_message = db.Column(db.Text)

    def __repr__(self):
        return f'<Job {self.id}>'

def create_db_tables_and_default_user():
    with app.app_context():
        app.logger.info("Verificando/Creando tablas de la base de datos SQLAlchemy...")
        db.create_all()
        app.logger.info("Tablas verificadas/creadas.")
        if User.query.filter_by(username="panthera").first() is None:
            hashed_password = generate_password_hash("panthera", method="pbkdf2:sha256")
            default_user = User(username="panthera", password=hashed_password)
            db.session.add(default_user)
            try:
                db.session.commit()
                app.logger.info("Usuario por defecto 'panthera' creado.")
            except Exception as e_user:
                db.session.rollback()
                app.logger.error(f"Error al crear usuario por defecto: {e_user}", exc_info=True)

@app.cli.command("init-db")
def init_db_sqlalchemy_command():
    click.echo("Inicializando la base de datos con SQLAlchemy...")
    create_db_tables_and_default_user()
    click.echo(f"Base de datos SQLAlchemy inicializada en {os.path.join(INSTANCE_FOLDER_PATH, DB_NAME)}.")

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=int(user_id)).first()


def run_scan_process(
    flask_app_instance, job_id, job_path_str, targets,
    selected_tools_config_list, advanced_options,
    tool_definitions_for_thread, app_logger,
):
    app_logger.info(f"Motor de escaneo (run_scan_process) iniciado para job {job_id} en {job_path_str}")
    job_path = Path(job_path_str)
    tool_outputs_dir = job_path / "tool_outputs"
    os.makedirs(tool_outputs_dir, exist_ok=True)
    initial_targets_file_path = job_path / f"{job_id}_initial_targets.txt"
    try:
        with open(initial_targets_file_path, "w", encoding="utf-8") as f_targets:
            for t_item in targets: f_targets.write(f"{t_item}\n")
        app_logger.info(f"Job {job_id}: Archivo de targets iniciales creado: {initial_targets_file_path}")
    except IOError as e: app_logger.error(f"Job {job_id}: Error creando archivo targets: {e}")

    current_summary_data = helpers.get_scan_status_from_file(str(job_path))
    with flask_app_instance.app_context():
        try:
            job_to_update = db.session.get(Job, job_id) # SQLAlchemy 2.0 way
            if job_to_update:
                current_time_iso = datetime.datetime.now().isoformat()
                job_to_update.status = "RUNNING"; job_to_update.start_timestamp = current_time_iso
                db.session.commit()
                current_summary_data.update({"status": "RUNNING", "start_timestamp": current_time_iso})
                current_summary_data["logs"].append({"timestamp": current_time_iso, "message": f"Job {job_id} ha comenzado a ejecutarse.", "level": "info", "is_html": False})
                helpers.save_job_summary(str(job_path), current_summary_data)
            else:
                app_logger.error(f"Job {job_id} no encontrado en DB al marcar RUNNING."); return "ERROR"
        except Exception as e:
            db.session.rollback(); app_logger.error(f"Job {job_id}: Error DB actualizando a RUNNING: {e}", exc_info=True); return "ERROR"

    total_tools_to_run = len(targets) * len(selected_tools_config_list)
    completed_tools_count = 0
    final_job_status_engine = "ERROR"

    try:
        for target_item in targets:
            for tool_config_entry in selected_tools_config_list:
                tool_id = tool_config_entry["id"]
                user_cli_params = tool_config_entry.get("cli_params", {})
                user_add_args = tool_config_entry.get("additional_args", "").strip()
                tool_def = tool_definitions_for_thread.get(tool_id)

                if not tool_def:
                    app_logger.warning(f"Job {job_id}: Definición no encontrada para {tool_id}. Saltando.")
                    current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(),"message": f"Definición herramienta {tool_id} no encontrada.","level": "warn", "is_html": False})
                    completed_tools_count += 1; continue

                with flask_app_instance.app_context():
                    job_db = db.session.get(Job, job_id) # SQLAlchemy 2.0 way
                    if job_db and job_db.status in ["REQUEST_CANCEL", "CANCELLED"]:
                        app_logger.info(f"Cancelación detectada para job {job_id}. Herramienta {tool_id} en {target_item} no se ejecutará.")
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(),"message": f"Escaneo cancelado antes de ejecutar {tool_def.get('name', tool_id)} en {target_item}.","level": "warn", "is_html": False})
                        helpers.save_job_summary(str(job_path), current_summary_data)
                        final_job_status_engine = "CANCELLED"; return final_job_status_engine

                filename_base = f"{tool_id}_{target_item.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}"
                cmd_template = tool_def.get("command_template", "")
                if not cmd_template:
                    app_logger.warning(f"Job {job_id}: No command template for tool {tool_id}. Saltando.")
                    completed_tools_count += 1; continue

                cmd_str = cmd_template
                for ph_key, _ in helpers.TARGET_PLACEHOLDERS_MAP.items(): # Use defined map
                     if ph_key in ["{target_file_subdomains}", "{target_file_live_hosts}", "{target_wordlist_file_massdns}"]:
                         cmd_str = cmd_str.replace(ph_key, shlex.quote(str(initial_targets_file_path)))
                     else:
                         cmd_str = cmd_str.replace(ph_key, shlex.quote(target_item))

                actual_out_path = tool_outputs_dir / f"{filename_base}.txt"
                if "{output_file_json}" in cmd_template: actual_out_path = tool_outputs_dir / f"{filename_base}.json"
                elif "{output_file_xml}" in cmd_template: actual_out_path = tool_outputs_dir / f"{filename_base}.xml"
                elif "{output_file_dir_sqlmap}" in cmd_template:
                    sqlmap_out_dir = tool_outputs_dir / f"{filename_base}_sqlmap_data"; os.makedirs(sqlmap_out_dir, exist_ok=True)
                    cmd_str = cmd_str.replace("{output_file_dir_sqlmap}", shlex.quote(str(sqlmap_out_dir))); actual_out_path = sqlmap_out_dir
                elif "{output_file_dir}" in cmd_template: actual_out_path = tool_outputs_dir
                
                output_ph_map = {
                    "{output_file}": str(tool_outputs_dir / f"{filename_base}.txt"), "{output_file_base}": str(tool_outputs_dir / filename_base),
                    "{output_file_json}": str(tool_outputs_dir / f"{filename_base}.json"), "{output_file_xml}": str(tool_outputs_dir / f"{filename_base}.xml"),
                    "{output_file_dir}": str(tool_outputs_dir)}
                for ph, p_val in output_ph_map.items(): cmd_str = cmd_str.replace(ph, shlex.quote(p_val))

                if tool_def.get("cli_params_config"):
                    for p_conf in tool_def["cli_params_config"]:
                        p_name = p_conf["name"]; placeholder = f"{{{p_name}}}"
                        u_val = user_cli_params.get(p_name); fin_val = u_val if u_val is not None else p_conf.get("default")
                        insert_s = ""
                        if p_conf["type"] == "checkbox": insert_s = p_conf.get("cli_true","") if bool(fin_val) else p_conf.get("cli_false","")
                        elif p_conf["type"] == "textarea" and p_conf.get("cli_format") and fin_val:
                            lines = [shlex.quote(l.strip()) for l in str(fin_val).splitlines() if l.strip()]
                            insert_s = " ".join([p_conf["cli_format"].replace("{value}",l) for l in lines])
                        elif fin_val is not None and str(fin_val).strip() != "": insert_s = shlex.quote(str(fin_val))
                        elif fin_val == "" and p_conf.get("type")!="password": insert_s = "" # Allow empty for non-passwords
                        if placeholder in cmd_str: cmd_str = cmd_str.replace(placeholder, insert_s.strip())
                
                cmd_str = re.sub(r"\{[a-zA-Z0-9_]+\}", "", cmd_str); cmd_str = ' '.join(cmd_str.split())
                final_cmd_list, final_cmd_log = [], ""
                needs_shell = tool_def.get("needs_shell", False)
                try:
                    if not needs_shell:
                        final_cmd_list = shlex.split(cmd_str)
                        if user_add_args: final_cmd_list.extend(shlex.split(user_add_args))
                        final_cmd_log = subprocess.list2cmdline(final_cmd_list)
                    else:
                        final_cmd_log = cmd_str + (f" {user_add_args}" if user_add_args else "")
                        final_cmd_list = final_cmd_log
                except ValueError as e:
                    app_logger.error(f"Job {job_id}: Shlex error {tool_id}: {e}. Cmd:'{cmd_str}', Args:'{user_add_args}'")
                    current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(),"message": f"Error parseando comando para {tool_def.get('name',tool_id)}: {e}","level": "error", "is_html": False })
                    current_summary_data["tool_progress"][f"{tool_id}_on_{target_item}"] = {"name":tool_def.get('name',tool_id),"id":tool_id,"status":"error","error_message":f"Shlex parse error: {e}","command":f"{cmd_str} {user_add_args}".strip()}
                    helpers.save_job_summary(str(job_path), current_summary_data)
                    completed_tools_count +=1; continue
                
                base_exe = final_cmd_list[0] if isinstance(final_cmd_list,list) and final_cmd_list else (final_cmd_list.split(" ")[0] if isinstance(final_cmd_list,str) else None)
                if not base_exe or not shutil.which(base_exe):
                    error_msg_nf = f"Herramienta ejecutable '{base_exe or 'desconocido'}' no encontrada en PATH."
                    app_logger.error(f"Job {job_id}: {error_msg_nf}")
                    current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": error_msg_nf, "level": "error", "is_html": False})
                    current_summary_data["tool_progress"][f"{tool_id}_on_{target_item}"] = {"status":"skipped","error_message":error_msg_nf,"name":tool_def.get('name',tool_id),"id":tool_id,"command":final_cmd_log}
                    helpers.save_job_summary(str(job_path), current_summary_data)
                    completed_tools_count += 1; continue

                app_logger.info(f"Job {job_id}: Ejecutando [{tool_def.get('name', tool_id)}] en [{target_item}]: {final_cmd_log}")
                current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Ejecutando: {final_cmd_log}","level":"command","is_html":False})
                tool_prog_key = f"{tool_id}_on_{target_item}"
                current_summary_data["tool_progress"][tool_prog_key] = {"id":tool_id,"name":tool_def.get('name',tool_id),"status":"running","command":final_cmd_log,"start_time":datetime.datetime.now().isoformat(),"output_file":None,"error_message":None}
                helpers.save_job_summary(str(job_path), current_summary_data)

                timeout_s = 3600
                tool_def_timeout = tool_def.get("timeout"); adv_opt_timeout = advanced_options.get("tool_timeout")
                if isinstance(tool_def_timeout,(int,float)) and tool_def_timeout>0 : timeout_s = tool_def_timeout
                if adv_opt_timeout is not None:
                    try:
                        parsed_adv = int(str(adv_opt_timeout).strip())
                        if parsed_adv > 0: timeout_s = parsed_adv
                        else: app_logger.warning(f"Job {job_id}: Timeout adv '{adv_opt_timeout}' <=0. Usando {timeout_s}s.")
                    except ValueError: app_logger.warning(f"Job {job_id}: Timeout adv '{adv_opt_timeout}' inválido. Usando {timeout_s}s.")
                final_timeout_subproc = int(timeout_s)
                app_logger.info(f"Job {job_id}: Timeout efectivo para {tool_id} en {target_item} es {final_timeout_subproc}s.")

                tool_status, tool_err_msg = "error", ""
                try:
                    proc = subprocess.run(final_cmd_list, shell=needs_shell, capture_output=True, text=True, timeout=final_timeout_subproc, check=False, cwd=str(tool_outputs_dir))
                    raw_log_path=tool_outputs_dir/f"{filename_base}_raw.log"
                    with open(raw_log_path,"w",encoding="utf-8") as f_raw:
                        f_raw.write(f"---Cmd---\n{final_cmd_log}\n\n---Code: {proc.returncode}---\n\n---STDOUT---\n{proc.stdout or '<no_stdout>'}\n\n---STDERR---\n{proc.stderr or '<no_stderr>'}\n\n")
                    if not any(p in cmd_template for p in helpers.OUTPUT_PLACEHOLDERS_LIST) and isinstance(actual_out_path,Path) and not actual_out_path.is_dir():
                        if proc.stdout:
                            with open(actual_out_path,"w",encoding="utf-8") as f_tool_out: f_tool_out.write(proc.stdout)
                    if proc.returncode == 0:
                        tool_status = "completed"
                        current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"{tool_def.get('name',tool_id)} en {target_item} completado.","level":"success","is_html":False})
                    else:
                        tool_status="error";tool_err_msg = f"Exit code {proc.returncode}. Stderr: {proc.stderr[:250]}..." if proc.stderr else f"Exit code {proc.returncode}."
                        current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Error en {tool_def.get('name',tool_id)} en {target_item}: {tool_err_msg}","level":"error","is_html":False})
                except subprocess.TimeoutExpired:
                    tool_status, tool_err_msg = "timeout", "Timeout Expirado"
                    app_logger.warning(f"Job {job_id}: Timeout para {tool_id} en {target_item}.")
                    current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Timeout para {tool_def.get('name',tool_id)} en {target_item}.","level":"error","is_html":False})
                    if isinstance(actual_out_path,Path) and not actual_out_path.is_dir():
                        try: open(actual_out_path,"a",encoding="utf-8").write("\n\n--- ERROR: TIMEOUT EXPIRED ---")
                        except Exception: pass
                except Exception as e_run:
                    tool_status, tool_err_msg = "error", str(e_run)
                    app_logger.error(f"Job {job_id}: Excepción ejecutando {tool_id} en {target_item}: {e_run}", exc_info=True)
                    current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Excepción en {tool_def.get('name',tool_id)} en {target_item}: {e_run}","level":"error","is_html":False})
                    if isinstance(actual_out_path,Path) and not actual_out_path.is_dir():
                        try: open(actual_out_path,"a",encoding="utf-8").write(f"\n\n--- EXCEPTION: {e_run} ---")
                        except Exception: pass
                
                completed_tools_count += 1
                prog = int((completed_tools_count/total_tools_to_run)*100) if total_tools_to_run > 0 else 0
                out_file_report = None
                if isinstance(actual_out_path, Path):
                    if actual_out_path.is_file() and actual_out_path.stat().st_size>0: out_file_report = str(actual_out_path.name)
                    elif actual_out_path.is_dir(): out_file_report = str(actual_out_path.name) + "/"
                
                current_summary_data["tool_progress"][tool_prog_key].update({"status":tool_status,"output_file":out_file_report,"end_time":datetime.datetime.now().isoformat(),"error_message":tool_err_msg or None})
                current_summary_data["overall_progress"] = prog
                helpers.save_job_summary(str(job_path), current_summary_data)

                with flask_app_instance.app_context():
                    job_prog_upd = db.session.get(Job, job_id) # SQLAlchemy 2.0
                    if job_prog_upd: job_prog_upd.overall_progress = prog;
                    try: db.session.commit()
                    except Exception as e: db.session.rollback(); app_logger.error(f"Job {job_id}: Error DB actualizando progreso: {e}", exc_info=True)
        
        final_job_status_engine = "COMPLETED"
        if any(tp.get("status", "error") in ["error", "timeout", "skipped"] for tp in current_summary_data.get("tool_progress", {}).values()):
            final_job_status_engine = "COMPLETED_WITH_ERRORS"
    except Exception as e:
        app_logger.error(f"Error mayor en motor para job {job_id}: {e}", exc_info=True)
        current_summary_data["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Error crítico del motor: {e}","level":"error","is_html":False})
        current_summary_data["error_message"] = str(e); final_job_status_engine = "ERROR"
    finally:
        current_summary_data.update({"status":final_job_status_engine, "end_timestamp":datetime.datetime.now().isoformat()})
        if final_job_status_engine != "CANCELLED": current_summary_data["overall_progress"] = 100
        helpers.save_job_summary(str(job_path), current_summary_data)
    return final_job_status_engine

def scan_job_thread_target(
    flask_app_instance, job_id, job_path, targets, selected_tools_config,
    advanced_options, tool_definitions, app_logger_for_thread,
):
    final_status, error_msg, progress_exit = "ERROR", None, 0
    with flask_app_instance.app_context():
        try:
            final_status = run_scan_process(flask_app_instance, job_id, job_path, targets, selected_tools_config, advanced_options, tool_definitions, app_logger_for_thread)
        except Exception as e:
            app_logger_for_thread.error(f"Excepción no controlada en hilo {job_id}: {e}", exc_info=True)
            final_status, error_msg = "ERROR", str(e)
            progress_exit = helpers.get_scan_status_from_file(job_path).get("overall_progress", 0)
        finally:
            active_scan_threads.pop(job_id, None)
            job_final = db.session.get(Job, job_id) # SQLAlchemy 2.0
            if job_final:
                job_final.status, job_final.end_timestamp = final_status, datetime.datetime.now().isoformat()
                if final_status == "CANCELLED" and progress_exit == 0: progress_exit = helpers.get_scan_status_from_file(job_path).get("overall_progress",0)
                job_final.overall_progress = 100 if final_status not in ["CANCELLED","REQUEST_CANCEL"] else progress_exit
                if error_msg: job_final.error_message = error_msg
                if final_status in ["COMPLETED", "COMPLETED_WITH_ERRORS", "CANCELLED"]:
                    job_path_obj = Path(job_path)
                    if job_path_obj.is_dir():
                        zip_base = f"{job_id}_results"; archive_path = Path(flask_app_instance.config["RESULTS_DIR"]) / zip_base
                        try:
                            shutil.make_archive(str(archive_path), "zip", str(job_path_obj.parent), job_path_obj.name)
                            app_root_prefix = flask_app_instance.config.get('APPLICATION_ROOT')
                            if app_root_prefix == '/': app_root_prefix = '' # Evitar doble slash
                            job_final.zip_path = f"{app_root_prefix or ''}/api/results/download/{zip_base}.zip"
                            app_logger_for_thread.info(f"ZIP creado: {job_final.zip_path}")
                            summary = helpers.get_scan_status_from_file(job_path); summary["zip_path"]=job_final.zip_path; helpers.save_job_summary(job_path,summary)
                        except Exception as e: app_logger_for_thread.error(f"Error creando ZIP {job_id}: {e}", exc_info=True)
                    else: app_logger_for_thread.error(f"Dir del job '{job_path}' no existe para ZIP.")
                try: db.session.commit(); app_logger_for_thread.info(f"Job {job_id} finalizado DB: {final_status}")
                except Exception as e: db.session.rollback(); app_logger_for_thread.error(f"Error commit final DB {job_id}: {e}", exc_info=True)
            else: app_logger_for_thread.error(f"Job {job_id} no encontrado para actualización final DB.")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("index"))
    if request.method == "POST":
        user_obj = User.query.filter_by(username=request.form["username"]).first()
        if user_obj and check_password_hash(user_obj.password, request.form["password"]):
            login_user(user_obj); flash("Inicio de sesión exitoso.", "success")
            return redirect(request.args.get("next") or url_for("index"))
        else: flash("Credenciales incorrectas.", "danger")
    return render_template("login.html", script_root=request.script_root or '')

@app.route("/logout")
@login_required
def logout(): logout_user(); flash("Has cerrado sesión.", "info"); return redirect(url_for("login"))

@app.route("/")
@login_required
def index(): return render_template("scans.html", script_root=request.script_root or '')

@app.route("/api/config", methods=["GET"])
@login_required
def get_app_config_route():
    try:
        return jsonify({"tools":helpers.get_tools_definition(),"profiles":helpers.get_scan_profiles(),"phases":helpers.get_pentest_phases(),"script_root":request.script_root or ''})
    except Exception as e: app.logger.error(f"Error config: {e}",exc_info=True); return jsonify({"error":"No se pudo cargar config."}),500

@app.route("/api/scan/start", methods=["POST"])
@login_required
def start_scan_route():
    data = request.get_json();
    if not data: return jsonify({"error": "Request JSON."}), 400
    targets_in = data.get("targets"); tools_payload = data.get("tools"); adv_opts = data.get("advanced_options",{})
    if not targets_in or not isinstance(targets_in,list) or not all(isinstance(t,str) for t in targets_in): return jsonify({"error":"Targets inválidos."}),400
    targets = [t.strip() for t in targets_in if t.strip()]
    if not targets: return jsonify({"error":"No targets válidos."}),400
    if not tools_payload or not isinstance(tools_payload,list): return jsonify({"error":"Herramientas inválidas."}),400
    for entry in tools_payload:
        if not isinstance(entry,dict) or "id" not in entry: return jsonify({"error":"Tool entry sin 'id'."}),400
        entry.setdefault("cli_params",{}); entry.setdefault("additional_args","")

    job_id = helpers.generate_job_id(); job_path = helpers.create_job_directories(app.config["RESULTS_DIR"],job_id)
    job_name = f"Scan: {', '.join(targets)[:50]}" + ("..." if len(targets[0]) > 50 or len(targets) > 1 else "")

    summary_data = {"job_id":job_id,"name":job_name,"user_id":current_user.id,"status":"PENDING","targets":targets,
                    "selected_tools_config":tools_payload,"advanced_options":adv_opts,"creation_timestamp":datetime.datetime.now().isoformat(),
                    "start_timestamp": None, "end_timestamp": None, "overall_progress": 0, # Explicitly add all fields
                    "results_path":str(job_path),"zip_path":None,"error_message":None,
                    "logs":[],"tool_progress":{}}
    summary_data["logs"].append({"timestamp": summary_data["creation_timestamp"], "message": f"Job {job_id} creado y en cola.", "level": "info", "is_html": False})
    
    tool_defs = helpers.get_tools_definition()
    for t_val in targets:
        for tool_e in tools_payload:
            t_id = tool_e['id']; t_name = tool_defs.get(t_id,{}).get('name',t_id)
            summary_data["tool_progress"][f"{t_id}_on_{t_val}"] = {"id":t_id,"name":t_name,"status":"pending", "command":None, "output_file":None, "start_time":None, "end_time":None, "error_message":None}
    helpers.save_job_summary(job_path,summary_data)
    try:
        new_job = Job(id=job_id,user_id=current_user.id,name=job_name,status="PENDING",targets=json.dumps(targets),
                      selected_tools_config=json.dumps(tools_payload),advanced_options=json.dumps(adv_opts),
                      creation_timestamp=summary_data["creation_timestamp"],results_path=str(job_path))
        db.session.add(new_job);db.session.commit()
    except Exception as e:
        db.session.rollback();app.logger.error(f"Error DB creando job {job_id}:{e}",exc_info=True)
        summary_err = helpers.get_scan_status_from_file(job_path); summary_err["status"] = "ERROR"
        summary_err["error_message"] = f"DB error: {e}"; helpers.save_job_summary(job_path, summary_err)
        return jsonify({"error":f"Error DB: {e}"}),500
    
    scan_thread = threading.Thread(target=scan_job_thread_target, args=(app,job_id,job_path,targets,tools_payload,adv_opts,tool_defs,app.logger),daemon=True)
    active_scan_threads[job_id]=scan_thread;scan_thread.start()
    try:
        job_init=db.session.get(Job, job_id) # SQLAlchemy 2.0
        if job_init:job_init.status="INITIALIZING";db.session.commit()
        s_init=helpers.get_scan_status_from_file(job_path);s_init["status"]="INITIALIZING"
        s_init["logs"].append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Job {job_id} inicializando.","level":"info","is_html":False})
        helpers.save_job_summary(job_path,s_init)
    except Exception as e: db.session.rollback();app.logger.error(f"Error DB actualizando {job_id} a INIT:{e}",exc_info=True)
    return jsonify({"message":"Trabajo iniciado.","job_id":job_id}),202

@app.route("/api/scan/status/<job_id>", methods=["GET"])
@login_required
def scan_status_route(job_id):
    is_admin = getattr(current_user,'id',None)==1
    job_q=Job.query.filter_by(id=job_id)
    if not is_admin: job_q=job_q.filter_by(user_id=current_user.id)
    job_db=job_q.first()
    if not job_db:
        s_fallback=helpers.get_scan_status_from_file(str(Path(app.config["RESULTS_DIR"])/job_id))
        if s_fallback.get("status")!="NOT_FOUND": return jsonify(s_fallback)
        return jsonify({"error":"Job no encontrado."}),404
    s_file=helpers.get_scan_status_from_file(job_db.results_path)
    return jsonify({"job_id":job_db.id,"name":job_db.name,"status":job_db.status,"overall_progress":job_db.overall_progress,
                    "start_time":job_db.start_timestamp or s_file.get("start_timestamp"),"end_time":job_db.end_timestamp,
                    "targets":json.loads(job_db.targets or "[]"),"logs":s_file.get("logs",[]),"tool_progress":s_file.get("tool_progress",{}),
                    "error_message":job_db.error_message or s_file.get("error_message"),"zip_path":job_db.zip_path})

@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    is_admin = getattr(current_user,'id',None)==1
    query = Job.query if is_admin else Job.query.filter_by(user_id=current_user.id)
    jobs = query.order_by(Job.creation_timestamp.desc()).all()
    return jsonify([{"id":j.id,"name":j.name,"status":j.status,"timestamp":j.start_timestamp or j.creation_timestamp,
                     "targets":json.loads(j.targets or "[]"),"overall_progress":j.overall_progress,"zip_path":j.zip_path} for j in jobs])

@app.route("/api/scan/cancel/<job_id>", methods=["POST"])
@login_required
def cancel_scan_route(job_id):
    is_admin=getattr(current_user,'id',None)==1
    job_q=Job.query.filter_by(id=job_id)
    if not is_admin: job_q=job_q.filter_by(user_id=current_user.id)
    job_cancel=job_q.first()
    if not job_cancel: return jsonify({"error":"Job no encontrado."}),404
    if job_cancel.status not in ["PENDING","INITIALIZING","RUNNING"]: return jsonify({"message":f"Job no cancelable (estado:{job_cancel.status})."}),400
    try:
        job_cancel.status="REQUEST_CANCEL";db.session.commit()
        summary=helpers.get_scan_status_from_file(job_cancel.results_path);summary["status"]="REQUEST_CANCEL"
        summary.setdefault("logs",[]).append({"timestamp":datetime.datetime.now().isoformat(),"message":f"Cancelación solicitada job {job_id}.","level":"warn","is_html":False})
        helpers.save_job_summary(job_cancel.results_path,summary)
        return jsonify({"message":f"Solicitud cancelación job {job_id} enviada."}),200
    except Exception as e: db.session.rollback();app.logger.error(f"Error DB cancelando {job_id}:{e}",exc_info=True);return jsonify({"error":"Error DB cancelando."}),500

@app.route("/api/results/download/<path:zip_filename>")
@login_required
def download_job_results_zip(zip_filename):
    if ".." in zip_filename or zip_filename.startswith("/"): return jsonify({"error":"Nombre archivo inválido."}),400
    is_admin=getattr(current_user,'id',None)==1
    app_root = app.config.get('APPLICATION_ROOT') or ''
    if app_root == '/': app_root = '' # Evitar doble slash si root es '/'
    expected_db_zip_path=f"{app_root}/api/results/download/{zip_filename}"
    
    job_q=Job.query.filter_by(zip_path=expected_db_zip_path)
    if not is_admin: job_q=job_q.filter_by(user_id=current_user.id)
    job_data=job_q.first()
    if not job_data: return jsonify({"error":"ZIP no encontrado/autorizado."}),404
    file_path=Path(app.config["RESULTS_DIR"])/zip_filename
    if not file_path.is_file(): return jsonify({"error":"ZIP no encontrado en servidor."}),404
    try: return send_file(str(file_path),as_attachment=True,download_name=zip_filename,mimetype="application/zip")
    except Exception as e: app.logger.error(f"Error enviando ZIP {zip_filename}:{e}",exc_info=True);return jsonify({"error":"No se pudo enviar ZIP."}),500

if __name__ == "__main__":
    db_file_path = Path(INSTANCE_FOLDER_PATH) / DB_NAME
    if not db_file_path.exists():
        app.logger.info(f"DB SQLAlchemy no encontrada en {db_file_path}. Creando con: flask init-db (debe ejecutarlo manualmente si esto es la primera vez o si este log persiste)")
        with app.app_context(): create_db_tables_and_default_user()
    else:
        with app.app_context(): db.create_all()
        app.logger.info(f"DB SQLAlchemy {db_file_path} ya existe o ha sido verificada.")

    env = os.environ.get("APP_ENV_MODE","PROD").upper(); host = os.environ.get("FLASK_RUN_HOST","0.0.0.0")
    try: port = int(os.environ.get("FLASK_RUN_PORT",5000))
    except ValueError: port=5000;app.logger.warning("FLASK_RUN_PORT inválido, usando 5000.")
    debug_mode = os.environ.get("FLASK_DEBUG","False").lower() in ["true","1","t","yes"]
    
    log_level = logging.DEBUG if (env=="DEBUG" or debug_mode) else logging.INFO
    app.logger.setLevel(log_level)
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=log_level,format='[%(asctime)s] %(levelname)s in %(module)s - %(funcName)s: %(message)s')
    else: # Si ya hay handlers, al menos ajustar el nivel del root logger
        logging.getLogger().setLevel(log_level)


    if env=="DEBUG":
        port=int(os.environ.get("FLASK_RUN_PORT",5001)); host="127.0.0.1"; debug_mode=True
    app.logger.info(f"MODO '{env}' activado. Escuchando en http://{host}:{port}. Debug Flask: {debug_mode}")
    
    app.run(host=host,port=port,debug=debug_mode)