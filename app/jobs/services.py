import logging
import sqlite3
import os
import datetime
import json
import threading
import shutil
from pathlib import Path

from utils import helpers 
from app.scanner_engine.engine import ScannerEngine # Importar ScannerEngine

class JobService:
    def __init__(self, db_path, jobs_base_dir, logger, tools_config, app_instance_path):
        self.db_path = db_path
        self.jobs_base_dir = Path(jobs_base_dir)
        self.logger = logger
        self.tools_config = tools_config 
        self.profiles_config = helpers.get_scan_profiles() # Usar la función de helpers
        self.app_instance_path = app_instance_path
        os.makedirs(self.jobs_base_dir, exist_ok=True)
        self.active_scan_threads = {} # Para rastrear hilos activos

    def _get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_job(self, targets, profile_id=None, selected_tools_payload=None, scan_name=None, advanced_options=None):
        if not targets:
            raise ValueError("Targets list cannot be empty.")
        if not profile_id and not selected_tools_payload: # Si no hay perfil, se deben enviar herramientas directamente
            raise ValueError("Either a profile_id or a list of selected_tools_payload must be provided.")

        job_id = helpers.get_current_timestamp_str() # Usar el generador de helpers
        job_path = self.jobs_base_dir / job_id
        os.makedirs(job_path, exist_ok=True)
        os.makedirs(job_path / "tool_outputs", exist_ok=True)

        current_time = datetime.datetime.now()
        scan_name = scan_name or f"Scan_{job_id}" # Nombre más simple
        
        tools_config_for_run = []

        if profile_id:
            profile = self.profiles_config.get(profile_id)
            if not profile:
                raise ValueError(f"Profile with id '{profile_id}' not found.")
            
            for tool_id_in_profile in profile.get('tools', []):
                tool_def = self.tools_config.get(tool_id_in_profile)
                if not tool_def:
                    self.logger.warning(f"Tool '{tool_id_in_profile}' from profile '{profile_id}' not found. Skipping.")
                    continue
                
                params_for_tool = {}
                if tool_def.get("cli_params_config"):
                    for p_conf in tool_def["cli_params_config"]:
                        params_for_tool[p_conf["name"]] = p_conf.get("default") # Empezar con defaults de la herramienta

                profile_overrides = profile.get("params_override", {}).get(tool_id_in_profile, {})
                params_for_tool.update(profile_overrides) # Sobrescribir con los del perfil
                
                additional_args_from_profile = profile_overrides.get("additional_args", "")

                tools_config_for_run.append({
                    "id": tool_id_in_profile, 
                    "cli_params": params_for_tool,
                    "additional_args": additional_args_from_profile # Añadir args adicionales del perfil
                })
        elif selected_tools_payload: # El frontend envía la estructura completa
            tools_config_for_run = selected_tools_payload
        
        if not tools_config_for_run:
            raise ValueError("No valid tools selected or configured for the scan.")

        initial_tool_progress = {}
        for target_val in targets:
            for tool_entry in tools_config_for_run:
                tool_id_for_prog = tool_entry['id']
                tool_def_for_name = self.tools_config.get(tool_id_for_prog, {})
                tool_name_for_prog = tool_def_for_name.get('name', tool_id_for_prog)
                tool_prog_key = f"{tool_id_for_prog}_on_{target_val}" # Clave única
                initial_tool_progress[tool_prog_key] = {
                    "id": tool_id_for_prog, # Guardar el ID para el frontend
                    "name": tool_name_for_prog, 
                    "status": "pending", 
                    "command": None, 
                    "output_file": None, 
                    "start_time": None, 
                    "end_time": None, 
                    "error_message": None,
                }

        job_summary_data = {
            "job_id": job_id,
            "name": scan_name,
            "status": "PENDING",
            "targets": targets,
            "profile_id": profile_id, # Guardar si se usó un perfil
            "selected_tools_config": tools_config_for_run, # Esta es la configuración que se usará
            "advanced_options": advanced_options or {},
            "creation_timestamp": current_time.isoformat(),
            "start_timestamp": None,
            "end_timestamp": None,
            "overall_progress": 0,
            "logs": [{"timestamp": current_time.isoformat(), "message": f"Job {job_id} creado y en cola.", "level": "info", "is_html": False}],
            "tool_progress": initial_tool_progress,
            "error_message": None,
            "results_path": str(job_path), # Guardar ruta al directorio del job
            "zip_path": None
        }
        helpers.save_job_summary(str(job_path), job_summary_data)

        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO job (id, user_id, name, status, targets, selected_tools_config, advanced_options, creation_timestamp, results_path, overall_progress)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, 1, scan_name, "PENDING", json.dumps(targets), # Asumiendo user_id 1 por ahora
                 json.dumps(tools_config_for_run), json.dumps(advanced_options or {}), 
                 current_time.isoformat(), str(job_path), 0)
            )
            conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating job {job_id}: {e}")
            shutil.rmtree(job_path, ignore_errors=True)
            raise Exception(f"Failed to record job {job_id} in database.") from e
        finally:
            if conn:
                conn.close()
        
        self.logger.info(f"Job {job_id} created for targets: {targets} with name: {scan_name}")
        return job_id, str(job_path)


    def start_job_processing(self, job_id):
        job_summary_path = self.jobs_base_dir / job_id / "summary.json"
        if not job_summary_path.exists():
            self.logger.error(f"Job summary for {job_id} not found at {job_summary_path}")
            return False

        try:
            with open(job_summary_path, 'r') as f:
                job_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading job summary for {job_id}: {e}")
            return False

        if job_data.get("status") not in ["PENDING", "ERROR", "CANCELLED", "COMPLETED_WITH_ERRORS"]: # Puede reintentar si falló
            self.logger.warning(f"Job {job_id} is not in a startable state (current: {job_data.get('status')}).")
            return False
        
        if job_id in self.active_scan_threads and self.active_scan_threads[job_id].is_alive():
            self.logger.warning(f"Job {job_id} is already running.")
            return False

        scanner_engine = ScannerEngine(self.logger, self.tools_config, self.db_path, self.app_instance_path)

        scan_thread = threading.Thread(
            target=scanner_engine.run_scan_process_entry,
            args=(
                job_id,
                str(self.jobs_base_dir / job_id),
                job_data["targets"],
                job_data["selected_tools_config"], # Usar la configuración guardada
                job_data["advanced_options"],
            ),
            daemon=True 
        )
        self.active_scan_threads[job_id] = scan_thread
        scan_thread.start()
        
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE job SET status = ? WHERE id = ?", ("INITIALIZING", job_id))
            conn.commit()
            job_data["status"] = "INITIALIZING"
            job_data["logs"].append({
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Job {job_id} ha comenzado la inicialización.",
                "level": "info", "is_html": False
            })
            helpers.save_job_summary(str(self.jobs_base_dir / job_id), job_data)
        except sqlite3.Error as e_update:
            self.logger.error(f"Error de DB al actualizar job {job_id} a INITIALIZING: {e_update}")
        finally:
            if conn: conn.close()

        self.logger.info(f"Scan thread started for job {job_id}")
        return True

    def get_all_jobs_summary(self):
        jobs = []
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, status, creation_timestamp, start_timestamp, overall_progress, zip_path, targets FROM job ORDER BY creation_timestamp DESC")
            db_jobs = cursor.fetchall()
            for row in db_jobs:
                job_summary = dict(row)
                try:
                    job_summary['targets'] = json.loads(row['targets']) if row['targets'] else []
                except (json.JSONDecodeError, TypeError):
                    job_summary['targets'] = [] # Fallback si no es JSON válido
                jobs.append(job_summary)
        except sqlite3.Error as e:
            self.logger.error(f"Database error listing jobs: {e}")
            raise
        finally:
            if conn:
                conn.close()
        return jobs

    def get_job_summary_data(self, job_id):
        job_path = self.jobs_base_dir / job_id
        conn = None
        db_data = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job WHERE id = ?", (job_id,))
            db_data = cursor.fetchone()
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching job {job_id} from DB: {e}")
        finally:
            if conn: conn.close()

        summary_from_file = helpers.get_scan_status_from_file(str(job_path))

        if not db_data and not summary_from_file.get('status') == 'NOT_FOUND':
            self.logger.warning(f"Job {job_id} found in summary file but not in DB. Returning file data.")
            return summary_from_file
        elif not db_data:
            return None # No existe en DB ni en archivo (o archivo indica NOT_FOUND)
        
        combined_summary = dict(db_data)
        combined_summary['targets'] = json.loads(db_data['targets']) if db_data['targets'] else summary_from_file.get('targets', [])
        combined_summary['logs'] = summary_from_file.get('logs', [])
        combined_summary['tool_progress'] = summary_from_file.get('tool_progress', {})
        combined_summary['error_message'] = db_data['error_message'] or summary_from_file.get('error_message')
        if 'selected_tools_config' in db_data and db_data['selected_tools_config']:
            try:
                combined_summary['selected_tools_config'] = json.loads(db_data['selected_tools_config'])
            except (json.JSONDecodeError, TypeError):
                 combined_summary['selected_tools_config'] = summary_from_file.get('selected_tools_config', [])
        else:
            combined_summary['selected_tools_config'] = summary_from_file.get('selected_tools_config', [])

        if 'advanced_options' in db_data and db_data['advanced_options']:
            try:
                combined_summary['advanced_options'] = json.loads(db_data['advanced_options'])
            except (json.JSONDecodeError, TypeError):
                combined_summary['advanced_options'] = summary_from_file.get('advanced_options', {})
        else:
            combined_summary['advanced_options'] = summary_from_file.get('advanced_options', {})


        return combined_summary


    def get_job_output_file_path(self, job_id, filename):
        if '..' in filename or filename.startswith('/'):
            self.logger.warning(f"Attempted path traversal for job {job_id}, filename {filename}")
            return None
        
        job_path = self.jobs_base_dir / job_id
        file_path = job_path / "tool_outputs" / filename
        
        try:
            resolved_job_outputs_dir = (job_path / "tool_outputs").resolve(strict=True)
            resolved_file_path = file_path.resolve(strict=True)
            if resolved_file_path.parent == resolved_job_outputs_dir and resolved_file_path.is_file():
                return str(resolved_file_path)
        except (FileNotFoundError, Exception) as e: # strict=True puede lanzar FileNotFoundError
            self.logger.warning(f"File resolution error for {filename} in job {job_id}: {e}")
            return None
        
        self.logger.warning(f"File {filename} not found or not accessible for job {job_id} at {file_path}")
        return None

    def request_cancel_job(self, job_id):
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM job WHERE id = ?", (job_id,))
            job_row = cursor.fetchone()
            if not job_row:
                self.logger.warning(f"Cancel request for non-existent job {job_id}")
                return False
            
            current_status = job_row['status']
            if current_status not in ["RUNNING", "PENDING", "INITIALIZING"]:
                self.logger.warning(f"Job {job_id} cannot be cancelled in state {current_status}")
                return False

            cursor.execute("UPDATE job SET status = ? WHERE id = ?", ("REQUEST_CANCEL", job_id))
            conn.commit()
            
            summary_data = self.get_job_summary_data(job_id) # Obtener el summary actual
            if summary_data:
                summary_data["status"] = "REQUEST_CANCEL" # Actualizar estado en el summary también
                summary_data.setdefault("logs", []).append({ # Asegurar que logs exista
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": "Cancel request received for job.",
                    "level": "warn", "is_html": False
                })
                helpers.save_job_summary(str(self.jobs_base_dir / job_id), summary_data)
            
            self.logger.info(f"Cancel requested for job {job_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"DB error requesting cancel for job {job_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def delete_job_data(self, job_id):
        job_path = self.jobs_base_dir / job_id
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM job WHERE id = ?", (job_id,))
            conn.commit()
            deleted_db_rows = cursor.rowcount > 0

            if job_path.exists():
                shutil.rmtree(job_path)
                self.logger.info(f"Job data directory {job_path} deleted for job {job_id}")
                return True 
            elif deleted_db_rows:
                self.logger.info(f"Job {job_id} deleted from DB, directory not found.")
                return True
            else:
                self.logger.warning(f"Job {job_id} not found for deletion (neither in DB nor on disk).")
                return False

        except sqlite3.Error as e:
            self.logger.error(f"DB error deleting job {job_id}: {e}")
            return False 
        except OSError as e:
            self.logger.error(f"OS error deleting job data for {job_id} at {job_path}: {e}")
            return False
        finally:
            if conn:
                conn.close()