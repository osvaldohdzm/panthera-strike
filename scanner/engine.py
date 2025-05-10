import subprocess
import os
import datetime
import shlex
import time
import shutil # Added import
from utils import get_tool_config # Importar la función para obtener la configuración de herramientas

MAX_CONCURRENT_TOOLS = 3 # Limitar concurrencia para no sobrecargar el sistema (12GB RAM)

def log_message(job_id, message, active_jobs, level='INFO'):
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry) # Log a consola del servidor
    if job_id in active_jobs:
        active_jobs[job_id]['logs'].append(log_entry)

def check_tool_installed(tool_name):
    """Verifica si una herramienta está instalada y es ejecutable usando shutil.which."""
    if shutil.which(tool_name):
        return True
    else:
        return False

def run_single_tool(job_id, target, tool_config, job_path, active_jobs):
    tool_name = tool_config['name']
    tool_command_template = tool_config['command']
    tool_category = tool_config['category']

    log_message(job_id, f"Preparando herramienta: {tool_name} para el objetivo: {target}", active_jobs)

    tool_output_dir = os.path.join(job_path, tool_category, tool_name + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    os.makedirs(tool_output_dir, exist_ok=True)
    
    output_file_name = f"output_{target.replace('/', '_').replace(':', '_')}.txt"
    output_file_path = os.path.join(tool_output_dir, output_file_name) # Default output file if tool writes to stdout

    format_kwargs = {'target': shlex.quote(target)}
    if '{output_file}' in tool_command_template:
        format_kwargs['output_file'] = shlex.quote(output_file_path)
    if '{output_file_dir}' in tool_command_template:
        format_kwargs['output_file_dir'] = shlex.quote(tool_output_dir)
    
    command_to_run = tool_command_template.format(**format_kwargs)

    log_message(job_id, f"Ejecutando: {command_to_run}", active_jobs)

    try:
        base_command = command_to_run.split()[0]
        if not check_tool_installed(base_command):
            log_message(job_id, f"ADVERTENCIA: La herramienta {base_command} no parece estar instalada o no está en el PATH. Saltando ejecución.", active_jobs, level='WARN')
            return {'tool': tool_name, 'target': target, 'status': 'skipped', 'error': f'{base_command} not found'}

        use_shell = tool_config.get('needs_shell', False)
        if use_shell:
            log_message(job_id, f"Ejecutando comando con shell=True: {command_to_run}", active_jobs, level='DEBUG')
            process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=job_path, shell=True)
        else:
            process = subprocess.Popen(shlex.split(command_to_run), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=job_path)
        
        stdout, stderr = process.communicate(timeout=300) # Timeout de 5 minutos por herramienta

        if process.returncode == 0:
            output_location_message = ''
            if '{output_file_dir}' in tool_command_template:
                output_location_message = f"Salida en directorio {tool_output_dir}"
            elif '{output_file}' in tool_command_template:
                output_location_message = f"Salida en archivo {output_file_path}"
            else:
                output_location_message = f"Salida (stdout/stderr) guardada en {output_file_path}"
            
            log_message(job_id, f"Herramienta {tool_name} completada para {target}. {output_location_message}", active_jobs)
            
            if '{output_file}' not in tool_command_template and '{output_file_dir}' not in tool_command_template and stdout:
                 with open(output_file_path, 'w') as f:
                    f.write(stdout)
            if stderr: # Guardar también errores si los hay
                with open(os.path.join(tool_output_dir, f"error_{target.replace('/', '_').replace(':', '_')}.txt"), 'w') as f:
                    f.write(stderr)
            return {'tool': tool_name, 'target': target, 'status': 'success', 'output_path': tool_output_dir}
        else:
            log_message(job_id, f"Error ejecutando {tool_name} para {target}. Código de salida: {process.returncode}", active_jobs, level='ERROR')
            log_message(job_id, f"Stderr: {stderr}", active_jobs, level='ERROR')
            with open(os.path.join(tool_output_dir, f"error_{target.replace('/', '_').replace(':', '_')}.txt"), 'w') as f:
                f.write(f"COMMAND: {command_to_run}\nRETURN_CODE: {process.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            return {'tool': tool_name, 'target': target, 'status': 'failed', 'error': stderr, 'output_path': tool_output_dir}

    except subprocess.TimeoutExpired:
        log_message(job_id, f"Timeout ejecutando {tool_name} para {target}", active_jobs, level='ERROR')
        return {'tool': tool_name, 'target': target, 'status': 'timeout', 'error': 'Timeout expired'}
    except Exception as e:
        log_message(job_id, f"Excepción ejecutando {tool_name} para {target}: {e}", active_jobs, level='ERROR')
        return {'tool': tool_name, 'target': target, 'status': 'exception', 'error': str(e)}

def run_scan(job_id, targets, job_path, targets_file_path, active_jobs, selected_tool_ids=None):
    log_message(job_id, f"Iniciando escaneo para el job {job_id} con objetivos: {targets}", active_jobs)
    if selected_tool_ids:
        log_message(job_id, f"Herramientas seleccionadas: {', '.join(selected_tool_ids)}", active_jobs)
    else:
        log_message(job_id, "No se seleccionaron herramientas específicas, se usarán las predeterminadas (MVP).", active_jobs)
    active_jobs[job_id]['status'] = 'running'
    all_results = []

    with open(targets_file_path, 'w') as f:
        for target_item in targets:
            f.write(f"{target_item}\n")
    log_message(job_id, f"Objetivos guardados en: {targets_file_path}", active_jobs)

    tool_configurations = get_tool_config()['raw_commands'] # Obtener todos los comandos de herramientas
    mvp_tool_keys = get_tool_config()['presets'].get('quick_scan', []) # Fallback a quick_scan si no hay seleccionadas

    tools_to_run = []
    if selected_tool_ids:
        for tool_id in selected_tool_ids:
            if tool_id in tool_configurations:
                tools_to_run.append(tool_configurations[tool_id])
            else:
                log_message(job_id, f"ADVERTENCIA: Herramienta con ID '{tool_id}' no encontrada en la configuración.", active_jobs, level='WARN')
    else:
        for tool_id in mvp_tool_keys:
            if tool_id in tool_configurations:
                tools_to_run.append(tool_configurations[tool_id])

    if not tools_to_run:
        log_message(job_id, "No hay herramientas válidas para ejecutar. Finalizando job.", active_jobs, level='ERROR')
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['end_time'] = datetime.datetime.now().isoformat()
        active_jobs[job_id]['error_message'] = 'No tools selected or configured to run.'
        summary_file = os.path.join(job_path, 'summary.json')
        with open(summary_file, 'w') as f:
            import json
            json.dump(active_jobs[job_id], f, indent=4, default=str)
        return


    for tool_conf in tools_to_run:
        log_message(job_id, f"Procesando herramienta: {tool_conf['name']} (Categoría: {tool_conf['category']})", active_jobs)
        for target_item in targets:
                if active_jobs[job_id]['status'] == 'cancelled': # Permitir cancelación
                    log_message(job_id, f"Job {job_id} cancelado.", active_jobs, level='WARN')
                    return
                
                result = run_single_tool(job_id, target_item, tool_conf, job_path, active_jobs)
                all_results.append(result)
                time.sleep(0.1)

    active_jobs[job_id]['status'] = 'completed'
    active_jobs[job_id]['end_time'] = datetime.datetime.now().isoformat()
    active_jobs[job_id]['results'] = all_results # Guardar un resumen de resultados
    log_message(job_id, f"Escaneo completado para el job {job_id}", active_jobs)

    summary_file = os.path.join(job_path, 'summary.json')
    with open(summary_file, 'w') as f:
        import json
        json.dump(active_jobs[job_id], f, indent=4, default=str)
    log_message(job_id, f"Resumen del job guardado en: {summary_file}", active_jobs)