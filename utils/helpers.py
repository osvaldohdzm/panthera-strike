import os
import datetime
import json
import shutil # Para shutil.move, que es similar a os.replace pero más universal

# Variable global para la configuración cacheada
_tool_config_cache = None
CONFIG_FILE_PATH = 'tools_config.json' # Ajusta la ruta si es necesario

def load_config_from_file():
    """Carga la configuración completa desde el archivo JSON."""
    global _tool_config_cache
    if _tool_config_cache is None:
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                _tool_config_cache = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Archivo de configuración '{CONFIG_FILE_PATH}' no encontrado.")
            # Podrías retornar una configuración por defecto o levantar una excepción
            _tool_config_cache = {"pentest_phases": {}, "tools_definition": {}, "scan_profiles": {}}
        except json.JSONDecodeError:
            print(f"ERROR: Error al decodificar JSON desde '{CONFIG_FILE_PATH}'.")
            _tool_config_cache = {"pentest_phases": {}, "tools_definition": {}, "scan_profiles": {}}
    return _tool_config_cache

def get_pentest_phases():
    config = load_config_from_file()
    return config.get("pentest_phases", {})

def get_tools_definition():
    config = load_config_from_file()
    # Enriquecer cada herramienta con su 'phase_name' basado en 'phase_key'
    phases = get_pentest_phases()
    tools_def = config.get("tools_definition", {})
    for tool_id, tool_data in tools_def.items():
        tool_data['phase'] = phases.get(tool_data.get('phase_key', ''), "Unknown Phase")
    return tools_def

def get_scan_profiles():
    config = load_config_from_file()
    return config.get("scan_profiles", {})

def create_job_directories(base_results_dir, job_id, targets):
    """Crea los directorios necesarios para un nuevo job de escaneo."""
    job_path = os.path.join(base_results_dir, job_id)
    os.makedirs(job_path, exist_ok=True)
    
    # Directorio para logs de herramientas individuales
    os.makedirs(os.path.join(job_path, 'tool_outputs'), exist_ok=True)

    targets_file_path = os.path.join(job_path, 'targets.txt')
    with open(targets_file_path, 'w', encoding='utf-8') as f:
        for target in targets:
            f.write(f"{target}\n")
    return job_path, targets_file_path

def get_scan_status_from_file(job_id, results_dir):
    """Obtiene el estado de un job de escaneo desde su summary.json."""
    job_path = os.path.join(results_dir, job_id)
    summary_file = os.path.join(job_path, 'summary.json')
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                status_info = json.load(f)
            return status_info
        except json.JSONDecodeError:
            return {'status': 'error', 'error_message': 'Could not parse summary file', 'job_id': job_id}
    return None # O un estado indicando 'not_found' o 'initializing'

def list_all_jobs(base_results_dir):
    """Lista todos los job IDs existentes basándose en directorios y summary.json."""
    if not os.path.exists(base_results_dir):
        return []
    
    job_details_list = []
    job_ids = [d for d in os.listdir(base_results_dir) if os.path.isdir(os.path.join(base_results_dir, d))]
    
    for job_id in job_ids:
        summary_path = os.path.join(base_results_dir, job_id, 'summary.json')
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                    job_details_list.append({
                        "id": summary_data.get("job_id", job_id),
                        "status": summary_data.get("status", "unknown"),
                        "timestamp": summary_data.get("start_time", ""), # O creation_time
                        "targets": summary_data.get("targets", []),
                        "zip_path": get_results_zip_path(job_id, base_results_dir) if summary_data.get("status") in ["COMPLETED", "CANCELLED"] else None
                        # Añadir más campos si es necesario para la lista
                    })
            except json.JSONDecodeError:
                job_details_list.append({
                    "id": job_id, "status": "error_summary_corrupt", "timestamp": "", "targets": []
                })
        else:
            # Directorio existe pero no summary.json, podría ser un job fallido o incompleto
             job_details_list.append({
                "id": job_id, "status": "incomplete_no_summary", "timestamp": "", "targets": []
            })

    # Ordenar por timestamp si está disponible, o por ID
    job_details_list.sort(key=lambda x: x.get("timestamp", x["id"]), reverse=True)
    return job_details_list


def get_current_timestamp_str():
    """Obtiene un timestamp formateado para nombres de archivo/directorio."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") # Added microseconds for uniqueness

def save_job_summary(job_path, job_data):
    """Guarda o actualiza el archivo summary.json del job de forma atómica."""
    summary_file_path = os.path.join(job_path, 'summary.json')
    temp_summary_file_path = summary_file_path + ".tmp"
    
    current_summary = {}
    if os.path.exists(summary_file_path):
        try:
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                current_summary = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Corrupted summary file at {summary_file_path}. Will overwrite.")
            current_summary = {} # Reset if corrupt

    # Deep merge logic for nested dictionaries like 'tool_progress'
    for key, value in job_data.items():
        if isinstance(value, dict) and isinstance(current_summary.get(key), dict):
            current_summary[key].update(value)
        elif isinstance(value, list) and key == 'logs': # Append to logs
            if key not in current_summary or not isinstance(current_summary[key], list):
                current_summary[key] = []
            current_summary[key].extend(value)
        else:
            current_summary[key] = value
    
    try:
        with open(temp_summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(current_summary, f, indent=4)
        shutil.move(temp_summary_file_path, summary_file_path) # Atomic replace
    except Exception as e:
        print(f"Error saving job summary for {job_data.get('job_id', 'Unknown Job')}: {e}")
        if os.path.exists(temp_summary_file_path):
            try:
                os.remove(temp_summary_file_path)
            except OSError:
                pass # Couldn't remove temp file, log or handle as needed
    return current_summary


def get_results_zip_path(job_id, results_dir):
    """Devuelve la ruta esperada para el archivo ZIP de resultados de un job."""
    # Asume que el ZIP se guarda en el directorio padre de los directorios de jobs
    # o en un directorio específico de "archives". Aquí lo pongo junto al dir del job.
    return os.path.join(results_dir, f"{job_id}_results.zip")

# Funciones para acceder a detalles de herramientas desde la config cacheada
def get_tool_details(tool_id):
    tools_def = get_tools_definition()
    return tools_def.get(tool_id, {})

def get_target_type_for_tool(tool_id):
    return get_tool_details(tool_id).get('target_type', 'domain_or_ip')

def tool_needs_shell(tool_id):
    return get_tool_details(tool_id).get('needs_shell', False)

def is_tool_dangerous(tool_id):
    return get_tool_details(tool_id).get('dangerous', False)

def get_tool_cli_params_config(tool_id):
    return get_tool_details(tool_id).get('cli_params_config', [])