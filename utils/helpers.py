import os
import datetime
import json

def create_job_directories(base_results_dir, job_id, targets):
    """Crea los directorios necesarios para un nuevo job de escaneo."""
    job_path = os.path.join(base_results_dir, job_id)
    os.makedirs(job_path, exist_ok=True)

    # Guardar los targets en un archivo dentro del directorio del job
    targets_file_path = os.path.join(job_path, 'targets.txt')
    with open(targets_file_path, 'w') as f:
        for target in targets:
            f.write(f"{target}\n")
    return job_path, targets_file_path

def get_scan_status(job_id, active_jobs, results_dir):
    """Obtiene el estado de un job de escaneo."""
    if job_id in active_jobs:
        return active_jobs[job_id]
    
    # Si no está en active_jobs (por ejemplo, si la app reinició), intentar leer del summary.json
    job_path = os.path.join(results_dir, job_id)
    summary_file = os.path.join(job_path, 'summary.json')
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r') as f:
                status_info = json.load(f)
            return status_info
        except json.JSONDecodeError:
            return {'status': 'unknown', 'error': 'Could not parse summary file'}
    return None

def get_job_logs(job_id, results_dir):
    """Intenta obtener los logs de un job, ya sea de active_jobs o del archivo de log principal del job si existe."""
    # Esta función es un placeholder. En una implementación real, los logs se manejarían de forma más robusta.
    # Por ahora, los logs están en active_jobs[job_id]['logs'] o podrían estar en un archivo job_id.log
    # Para este MVP, nos basaremos en lo que está en active_jobs si el job está activo.
    # Si el job ha terminado, el summary.json podría tener una copia de los logs o un puntero.

    # Simulación: si el job terminó, los logs podrían estar en un archivo. 
    # Aquí solo devolvemos un mensaje genérico si no está en active_jobs.
    # En app.py, los logs se añaden a active_jobs[job_id]['logs']
    # Esta función podría expandirse para leer de un archivo de log consolidado por job_id
    # Por ejemplo, leer de os.path.join(results_dir, job_id, 'job.log')
    
    # Para el MVP, los logs se gestionan en memoria en app.py y se guardan en summary.json
    # Esta función podría leer el summary.json para obtener los logs si el job no está activo.
    status = get_scan_status(job_id, {}, results_dir) # Usar {} para forzar lectura de archivo si no está activo
    if status and 'logs' in status:
        return status['logs']
    elif status:
        return [f"Logs for job {job_id} might be found in individual tool output files within {status.get('results_path', 'its result directory')}."]
    return None


def list_all_jobs(base_results_dir):
    """Lista todos los job IDs existentes escaneando el directorio de resultados."""
    if not os.path.exists(base_results_dir):
        return []
    job_ids = [d for d in os.listdir(base_results_dir) if os.path.isdir(os.path.join(base_results_dir, d))]
    # Opcional: filtrar por formato de job_id si es necesario, o simplemente devolver todos los directorios
    # Podríamos ordenarlos por fecha de creación si los nombres de directorio lo permiten (ej. si empiezan con fecha)
    job_ids.sort(reverse=True) # Mostrar los más recientes primero
    return job_ids


def get_tool_config():
    """Carga la configuración de herramientas. Podría ser desde un archivo YAML/JSON en el futuro."""
    # Esta es la lista completa de herramientas solicitada por el usuario.
    # Se necesita refinar los comandos exactos y cómo manejar la salida de cada una.
    # '{target}' y '{output_file}' son placeholders.
    # Algunas herramientas pueden necesitar argumentos específicos o no tener opción de output directo a archivo.

    tools_definition = {
        'amass_enum': {'name': 'Amass Enum', 'command': 'amass enum -d {target} -o {output_file}', 'category': 'Discovery', 'description': 'Descubrimiento de subdominios y enumeración de activos.'},
        'subfinder': {'name': 'Subfinder', 'command': 'subfinder -d {target} -o {output_file}', 'category': 'Discovery', 'description': 'Descubrimiento rápido de subdominios pasivos.'},
        'dnsx': {'name': 'DNSX', 'command': 'subfinder -d {target} -silent | dnsx -silent -resp -o {output_file}', 'category': 'Discovery', 'description': 'Herramienta rápida de DNS para resolver y consultar registros.', 'needs_shell': True},
        'naabu': {'name': 'Naabu', 'command': 'naabu -host {target} -silent -o {output_file}', 'category': 'Port Scan', 'description': 'Escáner de puertos rápido y simple.'},
        'httpx': {'name': 'HTTPX', 'command': 'httpx -silent -status-code -title -tech-detect -o {output_file} -u {target}', 'category': 'Web Info', 'description': 'Sonda HTTP rápida y multifuncional.'},
        'nmap_top_ports': {'name': 'Nmap Top Ports', 'command': 'nmap -sV -T4 --top-ports 1000 {target} -oA {output_file}', 'category': 'Port Scan', 'description': 'Escaneo de los 1000 puertos TCP más comunes con detección de versión y todos los formatos de salida.'},
        'nuclei': {'name': 'Nuclei', 'command': 'nuclei -u {target} -o {output_file} -silent', 'category': 'Vuln Scan', 'description': 'Escáner de vulnerabilidades basado en plantillas.'},
        'ffuf_common': {'name': 'FFUF Common Directories', 'command': 'ffuf -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -u {target}/FUZZ -o {output_file} -of csv -fs 0', 'category': 'Fuzzing', 'description': 'Fuzzing de directorios y archivos comunes.'},
        'dirsearch_common': {'name': 'Dirsearch Common', 'command': 'dirsearch -u {target} -e php,html,js,txt -w /usr/share/wordlists/dirb/common.txt --output={output_file} --format=simple', 'category': 'Fuzzing', 'description': 'Búsqueda de directorios y archivos web.'},
        'wpscan': {'name': 'WPScan', 'command': 'wpscan --ignore-main-redirect --url {target} --enumerate vp,vt,u --random-user-agent --api-token YOUR_WPSCAN_API_TOKEN -o {output_file} -f cli-no-color', 'category': 'CMS Scan', 'description': 'Escáner de vulnerabilidades de WordPress (requiere API token).', 'requires_api_token': True},
        'nikto': {'name': 'Nikto', 'command': 'nikto -h {target} -o {output_file} -Format txt', 'category': 'Vuln Scan', 'description': 'Escáner de vulnerabilidades web.'},
        'whatweb': {'name': 'WhatWeb', 'command': 'whatweb -a 3 {target} --log-brief {output_file}', 'category': 'Web Info', 'description': 'Identificación de tecnologías web.'},
        'wapiti': {'name': 'Wapiti', 'command': 'wapiti -u {target} -o {output_file_dir} -f txt --scope domain', 'category': 'Vuln Scan', 'description': 'Escáner de vulnerabilidades de aplicaciones web (black-box). Salida a directorio.'},
        'dirb': {'name': 'Dirb', 'command': 'dirb {target} /usr/share/wordlists/dirb/common.txt -o {output_file}', 'category': 'Fuzzing', 'description': 'Escáner de directorios web.'},
        'sqlmap_batch': {'name': 'SQLMap (Batch)', 'command': 'sqlmap -u "{target}" --batch --output-dir={output_file_dir} --results-file=results.txt', 'category': 'Exploitation', 'description': 'Detección y explotación de inyecciones SQL (modo batch). Peligroso.', 'dangerous': True},
    }

    # Herramientas seleccionadas para el MVP y para las opciones predefinidas
    # Estas son las claves de 'tools_definition'
    mvp_tool_keys = [
        'amass_enum',
        'subfinder',
        'dnsx',
        'naabu',
        'httpx',
        'nmap_top_ports',
        'nuclei',
        'nikto',
        'whatweb',
        'wapiti',
        'dirb'
    ]

    # Configuración para el frontend: una lista de diccionarios
    frontend_tools = []
    for key, tool_data in tools_definition.items():
        frontend_tools.append({
            'id': key, # Usar la clave como ID único
            'name': tool_data['name'],
            'category': tool_data['category'],
            'description': tool_data.get('description', 'N/A'),
            'default_enabled': key in mvp_tool_keys, # Marcar las herramientas MVP por defecto
            'requires_api_token': tool_data.get('requires_api_token', False),
            'dangerous': tool_data.get('dangerous', False)
        })

    # Definir conjuntos de herramientas para presets
    # Los IDs deben coincidir con las claves de 'tools_definition'
    presets = {
        'full_scan': [key for key in tools_definition.keys() if not tools_definition[key].get('dangerous') and not tools_definition[key].get('requires_api_token')], # Todas las seguras y sin API
        'quick_scan': ['subfinder', 'naabu', 'httpx', 'nmap_top_ports', 'nikto'], # Un subconjunto para escaneo rápido
        'discovery_only': ['amass_enum', 'subfinder', 'dnsx', 'naabu', 'httpx']
    }

    return {'tools': frontend_tools, 'presets': presets, 'raw_commands': tools_definition}


# ... existing code ...