import logging
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
import sqlite3

from utils import helpers # Asegurar que la importación es correcta

class ScannerEngine:
    def __init__(self, logger, tools_config, db_path, app_instance_path):
        self.logger = logger
        self.tools_config = tools_config # Diccionario completo de TOOLS_CONFIG
        self.db_path = db_path
        self.app_instance_path = app_instance_path # Para rutas absolutas si es necesario

    def _update_job_status_in_db(self, job_id, status, start_timestamp=None, end_timestamp=None):
        conn = None # Asegurar que conn esté definido
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if start_timestamp and status == "RUNNING":
                cursor.execute("UPDATE job SET status = ?, start_timestamp = ? WHERE id = ?", (status, start_timestamp, job_id))
            elif end_timestamp:
                cursor.execute("UPDATE job SET status = ?, end_timestamp = ? WHERE id = ?", (status, end_timestamp, job_id))
            else:
                cursor.execute("UPDATE job SET status = ? WHERE id = ?", (status, job_id))
            conn.commit()
        except sqlite3.Error as e_db_update:
            self.logger.error(f"Engine DB Update Error for Job {job_id}: Failed to update status to {status}: {e_db_update}")
        finally:
            if conn:
                conn.close()

    def _update_job_progress_in_db(self, job_id, progress):
        conn = None # Asegurar que conn esté definido
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE job SET overall_progress = ? WHERE id = ?", (progress, job_id))
            conn.commit()
        except sqlite3.Error as e_db_prog:
            self.logger.error(f"Engine DB Update Error for Job {job_id}: Failed to update progress: {e_db_prog}")
        finally:
            if conn:
                conn.close()

    def run_scan_process_entry(self, job_id, job_path_str, targets, selected_tools_config_list, advanced_options):
        """Punto de entrada para el hilo del motor de escaneo."""
        final_status_from_engine = "ERROR" # Default
        error_msg_thread = None
        try:
            final_status_from_engine = self.run_scan_process(
                job_id,
                job_path_str,
                targets,
                selected_tools_config_list,
                advanced_options,
                self.db_path,      # db_path_for_thread
                self.tools_config, # tool_definitions_for_thread
                self.logger        # app_logger
            )
        except Exception as e:
            self.logger.error(f"Excepción no controlada en el hilo del job {job_id}: {e}", exc_info=True)
            final_status_from_engine = "ERROR"
            error_msg_thread = str(e)
        finally:
            try:
                conn_final = sqlite3.connect(self.db_path)
                final_db_update_params = [final_status_from_engine, datetime.datetime.now().isoformat()]
                final_db_update_query = "UPDATE job SET status = ?, end_timestamp = ?"

                if final_status_from_engine not in ["CANCELLED", "REQUEST_CANCEL"]:
                    final_db_update_query += ", overall_progress = 100"
                
                if error_msg_thread:
                    final_db_update_query += ", error_message = ?"
                    final_db_update_params.append(error_msg_thread)
                
                final_db_update_query += " WHERE id = ?"
                final_db_update_params.append(job_id)
                
                conn_final.execute(final_db_update_query, tuple(final_db_update_params))
                conn_final.commit()
                self.logger.info(f"Job {job_id} finalizado en DB con estado: {final_status_from_engine}")

                if final_status_from_engine in ["COMPLETED", "COMPLETED_WITH_ERRORS", "CANCELLED"]:
                    job_path_obj = Path(job_path_str)
                    if not job_path_obj.is_dir():
                        self.logger.error(f"Error al crear ZIP para job {job_id}: El directorio del job '{job_path_str}' no existe.")
                        return

                    zip_filename_base = f"{job_id}_results"
                    archive_base_name_path = job_path_obj.parent / zip_filename_base 
                    archive_root_dir_path = job_path_obj.parent 
                    archive_item_name = job_path_obj.name 

                    try:
                        shutil.make_archive(
                            str(archive_base_name_path), 
                            "zip",
                            root_dir=str(archive_root_dir_path),
                            base_dir=archive_item_name
                        )
                        zip_url_path_for_db = f"/jobs/results/download/{zip_filename_base}.zip" # Ajustar si la ruta de descarga es diferente

                        conn_final.execute(
                            "UPDATE job SET zip_path = ? WHERE id = ?",
                            (zip_url_path_for_db, job_id),
                        )
                        conn_final.commit()
                        self.logger.info(f"Resultados para job {job_id} empaquetados en {archive_base_name_path}.zip")
                    except Exception as e_zip:
                        self.logger.error(f"Error al crear ZIP para job {job_id}: {e_zip}", exc_info=True)
                        summary_path_zip_err = job_path_obj / "summary.json"
                        s_data_zip_err = helpers.get_scan_status_from_file(str(summary_path_zip_err))
                        s_data_zip_err["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Error creando ZIP: {e_zip}",
                            "level": "error", "is_html": False
                        })
                        helpers.save_job_summary(str(job_path_obj), s_data_zip_err)
            except Exception as e_db_final:
                self.logger.error(f"Error CRÍTICO al actualizar estado final en DB para job {job_id}: {e_db_final}", exc_info=True)
            finally:
                if conn_final:
                    conn_final.close()


    def run_scan_process(
        self,
        job_id,
        job_path, 
        targets,
        selected_tools_config_list, 
        advanced_options,
        db_path_for_thread, # No se usa directamente aquí si los métodos _update_ usan self.db_path
        tool_definitions_for_thread, 
        app_logger, 
    ):
        app_logger.info(f"Motor de escaneo (run_scan_process) iniciado para job {job_id} en {job_path}")

        tool_outputs_dir = Path(job_path) / "tool_outputs"
        os.makedirs(tool_outputs_dir, exist_ok=True)

        current_summary_data = helpers.get_scan_status_from_file(job_path) 

        try:
            current_time_iso = datetime.datetime.now().isoformat()
            self._update_job_status_in_db(job_id, "RUNNING", start_timestamp=current_time_iso)
            
            current_summary_data["status"] = "RUNNING"
            current_summary_data["start_timestamp"] = current_time_iso
            current_summary_data["logs"].append({
                "timestamp": current_time_iso,
                "message": f"Job {job_id} ha comenzado a ejecutarse.",
                "level": "info", "is_html": False
            })
            helpers.save_job_summary(job_path, current_summary_data)
        except Exception as e_status:
            app_logger.error(f"Job {job_id}: Error al actualizar estado a RUNNING: {e_status}", exc_info=True)
            return "ERROR" 

        total_tools_to_run = len(targets) * len(selected_tools_config_list)
        completed_tools_count = 0
        
        final_job_status_engine = "ERROR" 

        try:
            for target_idx, target_item in enumerate(targets):
                target_value = target_item 

                for tool_config_entry in selected_tools_config_list:
                    tool_id = tool_config_entry["id"]
                    user_cli_params_for_tool = tool_config_entry.get("cli_params", {})
                    user_additional_args_str = tool_config_entry.get("additional_args", "") # NUEVO
                    tool_definition = tool_definitions_for_thread.get(tool_id)

                    if not tool_definition:
                        app_logger.warning(f"Job {job_id}: Definición no encontrada para herramienta {tool_id}. Saltando.")
                        current_summary_data["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Definición no encontrada para herramienta {tool_id}. Saltando.",
                            "level": "warn", "is_html": False
                        })
                        completed_tools_count += 1 
                        continue
                    
                    conn_check_cancel = None
                    try:
                        conn_check_cancel = sqlite3.connect(self.db_path) # Usar self.db_path
                        conn_check_cancel.row_factory = sqlite3.Row
                        cursor_cancel = conn_check_cancel.cursor()
                        cursor_cancel.execute("SELECT status FROM job WHERE id = ?", (job_id,))
                        job_status_db_check = cursor_cancel.fetchone()
                    except sqlite3.Error as e_db_check:
                        app_logger.error(f"Job {job_id}: Error al verificar estado de cancelación en DB: {e_db_check}")
                        job_status_db_check = None # Asumir que no se puede verificar, continuar con precaución
                    finally:
                        if cursor_cancel: cursor_cancel.close()
                        if conn_check_cancel: conn_check_cancel.close()


                    if job_status_db_check and job_status_db_check["status"] in ["REQUEST_CANCEL", "CANCELLED"]:
                        app_logger.info(f"Cancelación detectada para job {job_id}. Herramienta {tool_id} en {target_value} no se ejecutará.")
                        current_summary_data["logs"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "message": f"Escaneo cancelado antes de ejecutar {tool_definition.get('name', tool_id)} en {target_value}.",
                            "level": "warn", "is_html": False
                        })
                        helpers.save_job_summary(job_path, current_summary_data)
                        final_job_status_engine = "CANCELLED"
                        return final_job_status_engine

                    tool_output_filename_base = f"{tool_id}_{target_value.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}"
                    
                    command_template = tool_definition.get("command_template", "")
                    if not command_template:
                        app_logger.warning(f"Job {job_id}: No command template for tool {tool_id}")
                        completed_tools_count += 1
                        continue

                    current_command_str = command_template 

                    current_command_str = current_command_str.replace("{target}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_domain}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_url}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_host_or_ip}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_ip_range}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_domain_or_ip}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_wordpress_url}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_joomla_url}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_url_with_params}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_url_with_lfi_fuzz_param}", shlex.quote(target_value))
                    current_command_str = current_command_str.replace("{target_file_subdomains}", shlex.quote(str(Path(job_path) / "subdomains_for_httpx.txt"))) 
                    current_command_str = current_command_str.replace("{target_file_live_hosts}", shlex.quote(str(Path(job_path) / "live_hosts_for_httpx.txt"))) 
                    current_command_str = current_command_str.replace("{target_wordlist_file}", shlex.quote(str(Path(job_path) / "wordlist_for_massdns.txt"))) 

                    current_command_str = current_command_str.replace("{output_file}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.txt")))
                    current_command_str = current_command_str.replace("{output_file_base}", shlex.quote(str(tool_outputs_dir / tool_output_filename_base)))
                    current_command_str = current_command_str.replace("{output_file_json}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.json")))
                    current_command_str = current_command_str.replace("{output_file_xml}", shlex.quote(str(tool_outputs_dir / f"{tool_output_filename_base}.xml")))
                    current_command_str = current_command_str.replace("{output_file_dir}", shlex.quote(str(tool_outputs_dir)))

                    if tool_definition.get("cli_params_config"):
                        for p_conf in tool_definition["cli_params_config"]:
                            param_name = p_conf["name"]
                            placeholder = f"{{{param_name}}}"
                            value_from_frontend = user_cli_params_for_tool.get(param_name)
                            actual_param_value_str = ""

                            if p_conf["type"] == "checkbox":
                                is_checked = value_from_frontend if isinstance(value_from_frontend, bool) else p_conf.get("default", False)
                                if is_checked: actual_param_value_str = p_conf.get("cli_true", "")
                                else: actual_param_value_str = p_conf.get("cli_false", "")
                            
                            elif p_conf["type"] == "textarea":
                                text_value_to_process = value_from_frontend if value_from_frontend is not None else p_conf.get("default", "")
                                lines = [line.strip() for line in text_value_to_process.splitlines() if line.strip()]
                                formatted_lines = []
                                if p_conf.get("cli_format") and lines:
                                    for line in lines:
                                        formatted_lines.append(p_conf["cli_format"].replace("{value}", shlex.quote(line)))
                                    actual_param_value_str = " ".join(formatted_lines)
                                elif lines: 
                                    actual_param_value_str = " ".join([shlex.quote(l) for l in lines])
                            
                            else: 
                                final_value_for_param = value_from_frontend
                                if value_from_frontend is None or str(value_from_frontend).strip() == "":
                                    final_value_for_param = p_conf.get("default")
                                
                                if final_value_for_param is not None and str(final_value_for_param).strip() != "":
                                    actual_param_value_str = shlex.quote(str(final_value_for_param))
                            
                            current_command_str = current_command_str.replace(placeholder, actual_param_value_str.strip())

                    if tool_definition.get("cli_params_config"):
                        for p_conf in tool_definition["cli_params_config"]:
                            placeholder = f"{{{p_conf['name']}}}"
                            current_command_str = current_command_str.replace(placeholder, "") 
                    current_command_str = ' '.join(current_command_str.split())

                    final_command_list_for_exec = []
                    final_command_str_for_log = ""

                    if not tool_definition.get("needs_shell", False):
                        try:
                            final_command_list_for_exec = shlex.split(current_command_str)
                        except ValueError as e_shlex_final_base:
                            app_logger.error(f"Job {job_id}: Error al parsear comando base con params predefinidos para {tool_id}: {e_shlex_final_base}. Comando: {current_command_str}")
                            completed_tools_count += 1; continue 

                        if user_additional_args_str:
                            try:
                                additional_args_list = shlex.split(user_additional_args_str)
                                final_command_list_for_exec.extend(additional_args_list)
                            except ValueError:
                                app_logger.warning(f"Job {job_id}: Error al parsear argumentos adicionales '{user_additional_args_str}' para {tool_id} con shlex. Usando split simple.")
                                final_command_list_for_exec.extend(user_additional_args_str.split())
                        
                        final_command_str_for_log = subprocess.list2cmdline(final_command_list_for_exec)
                    
                    else: 
                        final_command_str_for_log = current_command_str 
                        if user_additional_args_str:
                            additional_args_list_for_shell = []
                            try:
                                additional_args_list_for_shell = [shlex.quote(arg) for arg in shlex.split(user_additional_args_str)]
                            except ValueError:
                                app_logger.warning(f"Job {job_id}: Error parseando args adicionales (shell) '{user_additional_args_str}' para {tool_id}. Usando split simple y quote.")
                                additional_args_list_for_shell = [shlex.quote(arg) for arg in user_additional_args_str.split()]
                            if additional_args_list_for_shell:
                                final_command_str_for_log += " " + " ".join(additional_args_list_for_shell)
                        
                        final_command_list_for_exec = final_command_str_for_log 

                    app_logger.info(f"Job {job_id}: Ejecutando [{tool_definition.get('name', tool_id)}] en [{target_value}]: {final_command_str_for_log}")
                    current_summary_data["logs"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Ejecutando {tool_definition.get('name', tool_id)}: {final_command_str_for_log}",
                        "level": "command", "is_html": False
                    })
                    
                    tool_prog_key = f"{tool_id}_on_{target_value}" 
                    current_summary_data["tool_progress"][tool_prog_key] = {
                        "id": tool_id, 
                        "name": tool_definition.get("name", tool_id), 
                        "status": "running", "command": final_command_str_for_log,
                        "start_time": datetime.datetime.now().isoformat(),
                        "output_file": None, "error_message": None
                    }
                    helpers.save_job_summary(job_path, current_summary_data)

                    tool_run_status = "error"; tool_error_message = ""
                    actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.txt" 
                    if "{output_file_json}" in tool_definition.get("command_template", ""): actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.json"
                    elif "{output_file_xml}" in tool_definition.get("command_template", ""): actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.xml"
                    elif "{output_file_dir}" in tool_definition.get("command_template", ""): actual_output_file_path = tool_outputs_dir

                    try:
                        default_tool_timeout_config = tool_definition.get("timeout")
                        if not isinstance(default_tool_timeout_config, (int, float)):
                            app_logger.warning(f"Job {job_id}: Timeout para {tool_id} no es un número ({default_tool_timeout_config}). Usando 3600s.")
                            default_tool_timeout_config = 3600 
                        
                        effective_timeout_str = advanced_options.get("tool_timeout")
                        
                        final_timeout_seconds = default_tool_timeout_config
                        if effective_timeout_str and str(effective_timeout_str).strip():
                            try:
                                final_timeout_seconds = int(effective_timeout_str)
                                if final_timeout_seconds <= 0:
                                    app_logger.warning(f"Job {job_id}: Timeout '{effective_timeout_str}' inválido (<=0). Usando {default_tool_timeout_config}s.")
                                    final_timeout_seconds = default_tool_timeout_config
                            except ValueError:
                                app_logger.warning(f"Job {job_id}: Valor de tool_timeout '{effective_timeout_str}' inválido. Usando {default_tool_timeout_config}s.")
                        
                        app_logger.debug(f"Job {job_id}: Usando timeout de {final_timeout_seconds}s para {tool_id}")

                        process = subprocess.run(
                            final_command_list_for_exec, 
                            shell=tool_definition.get("needs_shell", False),
                            capture_output=True, text=True,
                            timeout=final_timeout_seconds, 
                            check=False, cwd=str(tool_outputs_dir)
                        )

                        raw_log_path = tool_outputs_dir / f"{tool_output_filename_base}_raw.log"
                        with open(raw_log_path, "w", encoding="utf-8") as f_raw:
                            f_raw.write(f"--- Command ---\n{final_command_str_for_log}\n\n")
                            f_raw.write(f"--- Return Code: {process.returncode} ---\n\n")
                            f_raw.write(f"--- STDOUT ---\n{process.stdout or '<no stdout>'}\n\n")
                            f_raw.write(f"--- STDERR ---\n{process.stderr or '<no stderr>'}\n\n")

                        if not any(p in tool_definition.get("command_template", "") for p in ["{output_file}", "{output_file_base}", "{output_file_json}", "{output_file_xml}", "{output_file_dir}"]):
                            if process.stdout:
                                 with open(actual_output_file_path, "w", encoding="utf-8") as f_tool_out:
                                    f_tool_out.write(process.stdout)

                        if process.returncode == 0:
                            tool_run_status = "completed"
                            current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"{tool_definition.get('name', tool_id)} en {target_value} completado.", "level": "success", "is_html": False})
                        else:
                            tool_run_status = "error" 
                            tool_error_message = f"Exit code {process.returncode}. Stderr: {process.stderr[:250]}..." if process.stderr else f"Exit code {process.returncode}."
                            current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Error en {tool_definition.get('name', tool_id)} en {target_value}: {tool_error_message}", "level": "error", "is_html": False})
                    
                    except subprocess.TimeoutExpired:
                        tool_run_status = "timeout" 
                        tool_error_message = "Timeout Expirado"
                        app_logger.warning(f"Job {job_id}: Timeout para {tool_id} en {target_value}.")
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Timeout para {tool_definition.get('name', tool_id)} en {target_value}.", "level": "error", "is_html": False})
                        try:
                            with open(actual_output_file_path, "a", encoding="utf-8") as f_out_timeout: f_out_timeout.write("\n\n--- ERROR: TIMEOUT EXPIRED ---")
                        except Exception: pass

                    except Exception as e_tool_exec:
                        tool_run_status = "error"
                        tool_error_message = str(e_tool_exec)
                        app_logger.error(f"Job {job_id}: Excepción ejecutando {tool_id} en {target_value}: {e_tool_exec}", exc_info=True)
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Excepción en {tool_definition.get('name', tool_id)} en {target_value}: {e_tool_exec}", "level": "error", "is_html": False})
                        try:
                            with open(actual_output_file_path, "a", encoding="utf-8") as f_out_exc: f_out_exc.write(f"\n\n--- EXCEPTION: {e_tool_exec} ---")
                        except Exception: pass

                    completed_tools_count += 1
                    current_progress = int((completed_tools_count / total_tools_to_run) * 100) if total_tools_to_run > 0 else 0
                    
                    output_file_to_report = None
                    if Path(actual_output_file_path).is_file() and Path(actual_output_file_path).stat().st_size > 0 : 
                        output_file_to_report = str(Path(actual_output_file_path).name)
                    elif Path(actual_output_file_path).is_dir(): 
                         output_file_to_report = str(Path(actual_output_file_path).name) + "/" 

                    current_summary_data["tool_progress"][tool_prog_key].update({
                        "status": tool_run_status, "output_file": output_file_to_report,
                        "end_time": datetime.datetime.now().isoformat(),
                        "error_message": tool_error_message if tool_error_message else None,
                    })
                    current_summary_data["overall_progress"] = current_progress
                    helpers.save_job_summary(job_path, current_summary_data)

                    try: 
                        self._update_job_progress_in_db(job_id, current_progress)
                    except Exception as e_db_prog_loop:
                        app_logger.error(f"Job {job_id}: Error al actualizar progreso en DB (loop): {e_db_prog_loop}", exc_info=True)
            
            final_job_status_engine = "COMPLETED"
            if any(tp.get("status", "error") in ["error", "timeout"] for tp in current_summary_data.get("tool_progress", {}).values()):
                final_job_status_engine = "COMPLETED_WITH_ERRORS"

        except Exception as e_main_engine:
            app_logger.error(f"Error mayor en el motor de escaneo para job {job_id}: {e_main_engine}", exc_info=True)
            current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Error crítico del motor: {e_main_engine}", "level": "error", "is_html": False})
            current_summary_data["error_message"] = str(e_main_engine)
            final_job_status_engine = "ERROR"
        finally:
            helpers.save_job_summary(job_path, current_summary_data)
                
        return final_job_status_engine