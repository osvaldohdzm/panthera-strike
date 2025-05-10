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

from utils import helpers

class ScannerEngine:
    def __init__(self, logger, tools_config, db_path, app_instance_path):
        self.logger = logger
        self.tools_config = tools_config
        self.db_path = db_path
        self.project_root = Path(app_instance_path).parent if app_instance_path else Path.cwd()
        self.logger.debug(f"ScannerEngine initialized. Project root for config files: {self.project_root}")

    def _update_job_status_in_db(self, job_id, status, start_timestamp=None, end_timestamp=None, conn_to_use=None):
        close_conn_after = False
        if conn_to_use is None:
            conn_to_use = sqlite3.connect(self.db_path)
            close_conn_after = True
        try:
            cursor = conn_to_use.cursor()
            if start_timestamp and status == "RUNNING":
                cursor.execute("UPDATE job SET status = ?, start_timestamp = ? WHERE id = ?", (status, start_timestamp, job_id))
            elif end_timestamp:
                cursor.execute("UPDATE job SET status = ?, end_timestamp = ? WHERE id = ?", (status, end_timestamp, job_id))
            else:
                cursor.execute("UPDATE job SET status = ? WHERE id = ?", (status, job_id))
            conn_to_use.commit()
        except sqlite3.Error as e_db_update:
            self.logger.error(f"Engine DB Update Error for Job {job_id}: Failed to update status to {status}: {e_db_update}")
        finally:
            if close_conn_after and conn_to_use:
                conn_to_use.close()

    def _update_job_progress_in_db(self, job_id, progress, conn_to_use=None):
        close_conn_after = False
        if conn_to_use is None:
            conn_to_use = sqlite3.connect(self.db_path)
            close_conn_after = True
        
        try:
            cursor = conn_to_use.cursor()
            cursor.execute("UPDATE job SET overall_progress = ? WHERE id = ?", (progress, job_id))
            conn_to_use.commit()
        except sqlite3.Error as e_db_prog:
            self.logger.error(f"Engine DB Update Error for Job {job_id}: Failed to update progress: {e_db_prog}")
        finally:
            if close_conn_after and conn_to_use:
                conn_to_use.close()

    def run_scan_process_entry(self, job_id, job_path_str, targets, selected_tools_config_list, advanced_options):
        final_status_from_engine = "ERROR"
        error_msg_thread = None
        conn_thread_main = None
        try:
            conn_thread_main = sqlite3.connect(self.db_path)
            conn_thread_main.row_factory = sqlite3.Row

            final_status_from_engine = self.run_scan_process(
                job_id, job_path_str, targets, selected_tools_config_list,
                advanced_options, conn_thread_main, self.tools_config, self.logger
            )
        except Exception as e:
            self.logger.error(f"Excepción no controlada en el hilo del job {job_id}: {e}", exc_info=True)
            final_status_from_engine = "ERROR"
            error_msg_thread = str(e)
        finally:
            if conn_thread_main:
                conn_thread_main.close()
            
            conn_final_update = None
            try:
                conn_final_update = sqlite3.connect(self.db_path)
                cursor_final = conn_final_update.cursor()
                
                current_end_time = datetime.datetime.now().isoformat()
                current_progress_from_summary = self.get_job_progress_from_summary(job_path_str)
                final_progress = 100 if final_status_from_engine not in ["REQUEST_CANCEL", "CANCELLED"] else current_progress_from_summary

                update_query = "UPDATE job SET status = ?, end_timestamp = ?, overall_progress = ?"
                update_params = [final_status_from_engine, current_end_time, final_progress]

                if error_msg_thread:
                    update_query += ", error_message = ?"
                    update_params.append(error_msg_thread)
                
                update_query += " WHERE id = ?"
                update_params.append(job_id)
                
                cursor_final.execute(update_query, tuple(update_params))
                conn_final_update.commit()
                self.logger.info(f"Job {job_id} finalizado en DB con estado: {final_status_from_engine}, Progreso: {final_progress}%")

                if final_status_from_engine in ["COMPLETED", "COMPLETED_WITH_ERRORS", "CANCELLED"]:
                    self.create_job_zip(job_id, job_path_str, conn_final_update)

            except Exception as e_db_final:
                self.logger.error(f"Error CRÍTICO al actualizar estado final/ZIP en DB para job {job_id}: {e_db_final}", exc_info=True)
            finally:
                if conn_final_update:
                    conn_final_update.close()
    
    def get_job_progress_from_summary(self, job_path_str):
        summary = helpers.get_scan_status_from_file(job_path_str)
        return summary.get("overall_progress", 0)

    def create_job_zip(self, job_id, job_path_str, db_conn):
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
                str(archive_base_name_path), "zip",
                root_dir=str(archive_root_dir_path), base_dir=archive_item_name
            )
            zip_url_path_for_db = f"api/results/download/{zip_filename_base}.zip" 

            cursor = db_conn.cursor()
            cursor.execute("UPDATE job SET zip_path = ? WHERE id = ?", (zip_url_path_for_db, job_id))
            db_conn.commit()
            self.logger.info(f"Resultados para job {job_id} empaquetados en {archive_base_name_path}.zip. DB path: {zip_url_path_for_db}")
            
            summary_data = helpers.get_scan_status_from_file(job_path_str)
            summary_data["zip_path"] = zip_url_path_for_db
            helpers.save_job_summary(job_path_str, summary_data)

        except Exception as e_zip:
            self.logger.error(f"Error al crear ZIP para job {job_id}: {e_zip}", exc_info=True)
            summary_data = helpers.get_scan_status_from_file(job_path_str)
            summary_data.setdefault("logs", []).append({
                "timestamp": datetime.datetime.now().isoformat(),
                "message": f"Error creando ZIP: {e_zip}",
                "level": "error", "is_html": False
            })
            helpers.save_job_summary(job_path_str, summary_data)


    def run_scan_process(
        self, job_id, job_path_str, targets, selected_tools_config_list, 
        advanced_options, conn_thread, tool_definitions_for_thread, app_logger
    ):
        app_logger.info(f"Motor de escaneo (run_scan_process) iniciado para job {job_id} en {job_path_str}")
        job_path = Path(job_path_str)
        tool_outputs_dir = job_path / "tool_outputs"
        os.makedirs(tool_outputs_dir, exist_ok=True)

        initial_targets_file = job_path / f"{job_id}_initial_targets.txt"
        with open(initial_targets_file, "w", encoding="utf-8") as f_targets:
            for t_item in targets:
                f_targets.write(f"{t_item}\n")
        app_logger.info(f"Job {job_id}: Archivo de targets iniciales creado en {initial_targets_file}")

        current_summary_data = helpers.get_scan_status_from_file(str(job_path)) 

        try: 
            current_time_iso = datetime.datetime.now().isoformat()
            self._update_job_status_in_db(job_id, "RUNNING", start_timestamp=current_time_iso, conn_to_use=conn_thread)
            current_summary_data["status"] = "RUNNING"
            current_summary_data["start_timestamp"] = current_time_iso
            current_summary_data["logs"].append({"timestamp": current_time_iso, "message": f"Job {job_id} ha comenzado a ejecutarse.", "level": "info", "is_html": False})
            helpers.save_job_summary(str(job_path), current_summary_data)
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
                    user_additional_args_str = tool_config_entry.get("additional_args", "").strip()
                    tool_definition = tool_definitions_for_thread.get(tool_id)

                    if not tool_definition:
                        app_logger.warning(f"Job {job_id}: Definición no encontrada para herramienta {tool_id}. Saltando.")
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Definición no encontrada para herramienta {tool_id}. Saltando.", "level": "warn", "is_html": False})
                        completed_tools_count += 1; continue
                    
                    cursor_cancel = conn_thread.cursor()
                    cursor_cancel.execute("SELECT status FROM job WHERE id = ?", (job_id,))
                    job_status_db_check = cursor_cancel.fetchone()
                    cursor_cancel.close()

                    if job_status_db_check and job_status_db_check["status"] in ["REQUEST_CANCEL", "CANCELLED"]:
                        app_logger.info(f"Cancelación detectada para job {job_id}. Herramienta {tool_id} en {target_value} no se ejecutará.")
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Escaneo cancelado antes de ejecutar {tool_definition.get('name', tool_id)} en {target_value}.", "level": "warn", "is_html": False})
                        helpers.save_job_summary(str(job_path), current_summary_data)
                        final_job_status_engine = "CANCELLED"
                        return final_job_status_engine

                    tool_output_filename_base = f"{tool_id}_{target_value.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}"
                    command_template = tool_definition.get("command_template", "")
                    if not command_template:
                        app_logger.warning(f"Job {job_id}: No command template for tool {tool_id}")
                        completed_tools_count += 1; continue

                    current_command_str = command_template 
                    
                    target_placeholders = {
                        "{target}": target_value, "{target_domain}": target_value, "{target_url}": target_value,
                        "{target_host_or_ip}": target_value, "{target_ip_range}": target_value,
                        "{target_domain_or_ip}": target_value, "{target_wordpress_url}": target_value,
                        "{target_joomla_url}": target_value, "{target_url_with_params}": target_value,
                        "{target_url_with_lfi_fuzz_param}": target_value,
                        "{target_file_subdomains}": str(initial_targets_file),
                        "{target_file_live_hosts}": str(initial_targets_file),
                        "{target_wordlist_file_massdns}": str(initial_targets_file) 
                    }
                    for ph, val in target_placeholders.items():
                        current_command_str = current_command_str.replace(ph, shlex.quote(val))

                    actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.txt"
                    if "{output_file_json}" in command_template: actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.json"
                    elif "{output_file_xml}" in command_template: actual_output_file_path = tool_outputs_dir / f"{tool_output_filename_base}.xml"
                    elif "{output_file_dir_sqlmap}" in command_template:
                        sqlmap_tool_specific_dir = tool_outputs_dir / f"{tool_output_filename_base}_sqlmap_data"
                        os.makedirs(sqlmap_tool_specific_dir, exist_ok=True)
                        current_command_str = current_command_str.replace("{output_file_dir_sqlmap}", shlex.quote(str(sqlmap_tool_specific_dir)))
                        actual_output_file_path = sqlmap_tool_specific_dir
                    elif "{output_file_dir}" in command_template: actual_output_file_path = tool_outputs_dir
                    
                    output_placeholders_map = {
                        "{output_file}": str(tool_outputs_dir / f"{tool_output_filename_base}.txt"),
                        "{output_file_base}": str(tool_outputs_dir / tool_output_filename_base),
                        "{output_file_json}": str(tool_outputs_dir / f"{tool_output_filename_base}.json"),
                        "{output_file_xml}": str(tool_outputs_dir / f"{tool_output_filename_base}.xml"),
                        "{output_file_dir}": str(tool_outputs_dir) 
                    }
                    for ph, val_path_str in output_placeholders_map.items():
                        current_command_str = current_command_str.replace(ph, shlex.quote(val_path_str))
                    
                    param_flags_to_add_separately = []
                    if tool_definition.get("cli_params_config"):
                        for p_conf in tool_definition["cli_params_config"]:
                            param_name = p_conf["name"]
                            placeholder = f"{{{param_name}}}"
                            value_from_frontend = user_cli_params_for_tool.get(param_name)
                            final_value_for_param = value_from_frontend if value_from_frontend is not None else p_conf.get("default")
                            param_value_to_insert = ""

                            if p_conf["type"] == "checkbox":
                                is_checked = bool(final_value_for_param)
                                if is_checked: param_value_to_insert = p_conf.get("cli_true", "")
                                else: param_value_to_insert = p_conf.get("cli_false", "")
                            elif p_conf["type"] == "textarea" and p_conf.get("cli_format"):
                                text_value_to_process = str(final_value_for_param or "").strip()
                                lines = [line.strip() for line in text_value_to_process.splitlines() if line.strip()]
                                formatted_lines_for_cmd = []
                                if lines:
                                    for line in lines:
                                        formatted_lines_for_cmd.append(p_conf["cli_format"].replace("{value}", shlex.quote(line)))
                                    param_value_to_insert = " ".join(formatted_lines_for_cmd)
                            else: 
                                if final_value_for_param is not None and str(final_value_for_param).strip() != "":
                                    if param_name in ["ports_to_scan_file", "resolvers_file", "wordlist_path", "lfi_wordlist", "target_wordlist_file_massdns"]:
                                        config_file_rel_path = str(final_value_for_param)
                                        possible_paths = [
                                            self.project_root / "config" / Path(config_file_rel_path).name,
                                            self.project_root / "lists" / Path(config_file_rel_path).name,
                                            Path(config_file_rel_path) # Para rutas absolutas o relativas a CWD (menos ideal)
                                        ]
                                        resolved_path = None
                                        for p_path in possible_paths:
                                            if p_path.exists():
                                                resolved_path = p_path
                                                break
                                        if resolved_path:
                                            param_value_to_insert = shlex.quote(str(resolved_path))
                                        else:
                                            app_logger.error(f"Job {job_id}: Archivo de config '{param_name}' no encontrado en rutas probadas para valor '{config_file_rel_path}'. Usando valor original.")
                                            param_value_to_insert = shlex.quote(str(final_value_for_param))
                                    elif param_name == "wpscan_api_token_cmd" and str(final_value_for_param).strip():
                                        param_value_to_insert = f"--api-token {shlex.quote(str(final_value_for_param))}"
                                    elif param_name == "xsser_params_cmd" and str(final_value_for_param).strip():
                                         param_value_to_insert = f'--params "{shlex.quote(str(final_value_for_param))}"'
                                    else:
                                        param_value_to_insert = shlex.quote(str(final_value_for_param))
                                elif final_value_for_param == "" and p_conf.get("type") != "password":
                                     param_value_to_insert = "" 

                            if placeholder in current_command_str:
                                current_command_str = current_command_str.replace(placeholder, param_value_to_insert.strip())
                            elif param_value_to_insert.strip():
                                param_flags_to_add_separately.extend(shlex.split(param_value_to_insert.strip()))
                    
                    if tool_definition.get("cli_params_config"):
                        for p_conf in tool_definition["cli_params_config"]:
                            current_command_str = current_command_str.replace(f"{{{p_conf['name']}}}", "") 
                    current_command_str = ' '.join(current_command_str.split())

                    final_command_list_for_exec = []
                    final_command_str_for_log = ""

                    if not tool_definition.get("needs_shell", False):
                        try:
                            final_command_list_for_exec = shlex.split(current_command_str)
                            final_command_list_for_exec.extend(filter(None, param_flags_to_add_separately))
                            if user_additional_args_str:
                                final_command_list_for_exec.extend(shlex.split(user_additional_args_str))
                            final_command_str_for_log = subprocess.list2cmdline(final_command_list_for_exec)
                        except ValueError as e_shlex_final:
                            app_logger.error(f"Job {job_id}: Error al parsear comando final para {tool_id}: {e_shlex_final}. Comando: {current_command_str}")
                            completed_tools_count += 1; continue
                    else: 
                        final_command_str_for_log = current_command_str
                        if param_flags_to_add_separately:
                            final_command_str_for_log += " " + " ".join(filter(None, param_flags_to_add_separately))
                        if user_additional_args_str:
                            final_command_str_for_log += " " + user_additional_args_str
                        final_command_str_for_log = ' '.join(final_command_str_for_log.split())
                        final_command_list_for_exec = final_command_str_for_log
                    
                    base_executable_to_check = final_command_list_for_exec[0] if isinstance(final_command_list_for_exec, list) else final_command_list_for_exec.split(" ")[0]
                    if not shutil.which(base_executable_to_check):
                        error_msg_notfound = f"Herramienta '{base_executable_to_check}' no encontrada en PATH."
                        app_logger.error(f"Job {job_id}: {error_msg_notfound}")
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": error_msg_notfound, "level": "error", "is_html": False})
                        current_summary_data["tool_progress"][f"{tool_id}_on_{target_value}"] = {"status": "skipped", "error_message": error_msg_notfound, "name": tool_definition.get("name", tool_id), "id": tool_id}
                        helpers.save_job_summary(str(job_path), current_summary_data)
                        completed_tools_count += 1; continue

                    app_logger.info(f"Job {job_id}: Ejecutando [{tool_definition.get('name', tool_id)}] en [{target_value}]: {final_command_str_for_log}")
                    current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Ejecutando {tool_definition.get('name', tool_id)}: {final_command_str_for_log}", "level": "command", "is_html": False})
                    
                    tool_prog_key = f"{tool_id}_on_{target_value}" 
                    current_summary_data["tool_progress"][tool_prog_key] = {
                        "id": tool_id, "name": tool_definition.get("name", tool_id), 
                        "status": "running", "command": final_command_str_for_log,
                        "start_time": datetime.datetime.now().isoformat(),
                        "output_file": None, "error_message": None
                    }
                    helpers.save_job_summary(str(job_path), current_summary_data)

                    tool_run_status = "error"; tool_error_message = ""
                    
                    tool_timeout_value_config = tool_definition.get("timeout", 3600) 
                    effective_timeout_str_adv = advanced_options.get("tool_timeout")
                    final_timeout_seconds_tool = tool_timeout_value_config
                    if effective_timeout_str_adv and str(effective_timeout_str_adv).strip():
                        try:
                            parsed_adv_timeout = int(effective_timeout_str_adv)
                            if parsed_adv_timeout > 0: final_timeout_seconds_tool = parsed_adv_timeout
                            else: app_logger.warning(f"Job {job_id}: Timeout avanzado '{effective_timeout_str_adv}' inválido (<=0). Usando {tool_timeout_value_config}s.")
                        except ValueError:
                            app_logger.warning(f"Job {job_id}: Valor de tool_timeout '{effective_timeout_str_adv}' no es un número. Usando {tool_timeout_value_config}s.")
                    
                    app_logger.debug(f"Job {job_id}: Usando timeout de {final_timeout_seconds_tool}s para {tool_id}")

                    try:
                        process = subprocess.run(
                            final_command_list_for_exec, 
                            shell=tool_definition.get("needs_shell", False),
                            capture_output=True, text=True,
                            timeout=final_timeout_seconds_tool, 
                            check=False, cwd=str(tool_outputs_dir)
                        )
                        raw_log_path = tool_outputs_dir / f"{tool_output_filename_base}_raw.log"
                        with open(raw_log_path, "w", encoding="utf-8") as f_raw:
                            f_raw.write(f"--- Command ---\n{final_command_str_for_log}\n\n")
                            f_raw.write(f"--- Return Code: {process.returncode} ---\n\n")
                            f_raw.write(f"--- STDOUT ---\n{process.stdout or '<no stdout>'}\n\n")
                            f_raw.write(f"--- STDERR ---\n{process.stderr or '<no stderr>'}\n\n")

                        if not any(p in tool_definition.get("command_template", "") for p in ["{output_file}", "{output_file_base}", "{output_file_json}", "{output_file_xml}", "{output_file_dir}", "{output_file_dir_sqlmap}"]) \
                           and isinstance(actual_output_file_path, Path) and not actual_output_file_path.is_dir():
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
                            if isinstance(actual_output_file_path, Path) and not actual_output_file_path.is_dir():
                                with open(actual_output_file_path, "a", encoding="utf-8") as f_out_timeout: f_out_timeout.write("\n\n--- ERROR: TIMEOUT EXPIRED ---")
                        except Exception: pass

                    except Exception as e_tool_exec:
                        tool_run_status = "error"
                        tool_error_message = str(e_tool_exec)
                        app_logger.error(f"Job {job_id}: Excepción ejecutando {tool_id} en {target_value}: {e_tool_exec}", exc_info=True)
                        current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Excepción en {tool_definition.get('name', tool_id)} en {target_value}: {e_tool_exec}", "level": "error", "is_html": False})
                        try:
                            if isinstance(actual_output_file_path, Path) and not actual_output_file_path.is_dir():
                                with open(actual_output_file_path, "a", encoding="utf-8") as f_out_exc: f_out_exc.write(f"\n\n--- EXCEPTION: {e_tool_exec} ---")
                        except Exception: pass

                    completed_tools_count += 1
                    current_progress = int((completed_tools_count / total_tools_to_run) * 100) if total_tools_to_run > 0 else 0
                    
                    output_file_to_report = None
                    if isinstance(actual_output_file_path, Path):
                        if actual_output_file_path.is_file() and actual_output_file_path.stat().st_size > 0 : 
                            output_file_to_report = str(actual_output_file_path.name)
                        elif actual_output_file_path.is_dir(): 
                             output_file_to_report = str(actual_output_file_path.name) + "/" 

                    current_summary_data["tool_progress"][tool_prog_key].update({
                        "status": tool_run_status, "output_file": output_file_to_report,
                        "end_time": datetime.datetime.now().isoformat(),
                        "error_message": tool_error_message if tool_error_message else None,
                    })
                    current_summary_data["overall_progress"] = current_progress
                    helpers.save_job_summary(str(job_path), current_summary_data)
                    self._update_job_progress_in_db(job_id, current_progress, conn_to_use=conn_thread)
            
            final_job_status_engine = "COMPLETED"
            if any(tp.get("status", "error") in ["error", "timeout", "skipped"] for tp in current_summary_data.get("tool_progress", {}).values()):
                final_job_status_engine = "COMPLETED_WITH_ERRORS"

        except Exception as e_main_engine:
            app_logger.error(f"Error mayor en el motor de escaneo para job {job_id}: {e_main_engine}", exc_info=True)
            current_summary_data["logs"].append({"timestamp": datetime.datetime.now().isoformat(), "message": f"Error crítico del motor: {e_main_engine}", "level": "error", "is_html": False})
            current_summary_data["error_message"] = str(e_main_engine)
            final_job_status_engine = "ERROR"
        finally:
            current_summary_data["status"] = final_job_status_engine
            if final_job_status_engine != "CANCELLED": # No sobrescribir progreso si se canceló
                 current_summary_data["overall_progress"] = 100
            current_summary_data["end_timestamp"] = datetime.datetime.now().isoformat()
            helpers.save_job_summary(str(job_path), current_summary_data)
                
        return final_job_status_engine