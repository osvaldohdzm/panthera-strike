import os
import datetime
import json

# Define Pentesting Phases
PENTEST_PHASES = {
    "recon_passive": "🔍 Discovery - Passive Reconnaissance",
    "recon_active": "🎯 Discovery - Active Reconnaissance",
    "scanning_network": "📡 Network Scanning - Ports & Services",
    "web_fingerprint": "🌐 Web Recon & Fingerprinting",
    "web_vuln_scan": "🧪 Web Vulnerability Scanning",
    "infra_vuln_scan": "🛡️ Infrastructure Vulnerability Scanning",
    "cms_framework_scan": "📦 CMS & Framework Scanning",
    "fuzzing_discovery": "💣 Fuzzing & Directory Discovery",
    "exploitation_checks": "💥 Exploitation Checks (Automated)",
    "tls_ssl_analysis": "🔐 SSL/TLS Analysis",
    "bruteforce_creds": "🔑 Credential Access - Brute Force"
}


def create_job_directories(base_results_dir, job_id, targets):
    """Crea los directorios necesarios para un nuevo job de escaneo."""
    job_path = os.path.join(base_results_dir, job_id)
    os.makedirs(job_path, exist_ok=True)
    targets_file_path = os.path.join(job_path, 'targets.txt')
    with open(targets_file_path, 'w') as f:
        for target in targets:
            f.write(f"{target}\n")
    return job_path, targets_file_path

def get_scan_status(job_id, active_jobs, results_dir):
    """Obtiene el estado de un job de escaneo."""
    if job_id in active_jobs:
        return active_jobs[job_id]
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
    """Intenta obtener los logs de un job."""
    status = get_scan_status(job_id, {}, results_dir)
    if status and 'logs' in status:
        return status['logs']
    elif status:
        return [f"Logs for job {job_id} might be in individual tool output files within {status.get('results_path', 'its result directory')}."]
    return None

def list_all_jobs(base_results_dir):
    """Lista todos los job IDs existentes."""
    if not os.path.exists(base_results_dir):
        return []
    job_ids = [d for d in os.listdir(base_results_dir) if os.path.isdir(os.path.join(base_results_dir, d))]
    job_ids.sort(reverse=True)
    return job_ids

def get_tool_config():
    """Carga la configuración de herramientas con fases y categorías."""
    tools_definition = {
        # --- 🔍 Discovery - Passive Reconnaissance ---
        'subfinder': {
            'name': 'Subfinder', 'command_template': 'subfinder -d {target} -o {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'Subdomain Enumeration',
            'description': 'Enumeración rápida pasiva de subdominios.',
            'default_enabled': True
        },
        'assetfinder': {
            'name': 'Assetfinder', 'command_template': 'assetfinder --subs-only {target} > {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'Subdomain Enumeration',
            'description': 'Encuentra subdominios relacionados con una organización.', 'needs_shell': True
        },
        'findomain': {
            'name': 'Findomain', 'command_template': 'findomain -t {target} -u {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'Subdomain Enumeration',
            'description': 'Enumerador rápido de subdominios (Rust).',
        },
        'whois': {
            'name': 'Whois', 'command_template': 'whois {target} > {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'DNS & WHOIS',
            'description': 'Recolecta datos WHOIS.', 'needs_shell': True
        },
         'waybackurls': {
            'name': 'Waybackurls', 'command_template': 'echo {target} | waybackurls > {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'Historical URL Discovery',
            'description': 'URLs antiguas indexadas (Wayback Machine).', 'needs_shell': True
        },
        'gau': {
            'name': 'GAU (GetAllUrls)', 'command_template': 'gau {target} --o {output_file}',
            'phase': PENTEST_PHASES["recon_passive"], 'category': 'Historical URL Discovery',
            'description': 'Recopila URLs desde servicios OSINT.',
        },

        # --- 🎯 Discovery - Active Reconnaissance ---
        'amass_enum': {
            'name': 'Amass Enum', 'command_template': 'amass enum -d {target} -o {output_file}',
            'phase': PENTEST_PHASES["recon_active"], 'category': 'Subdomain Enumeration (Active)',
            'description': 'Enumeración activa y pasiva de subdominios.', 'default_enabled': True
        },
        'dnsrecon': {
            'name': 'DNSRecon', 'command_template': 'dnsrecon -d {target} -t std,srv,axfr -x {output_file_xml}',
            'phase': PENTEST_PHASES["recon_active"], 'category': 'DNS Enumeration',
            'description': 'Recolecta registros DNS comunes, intenta AXFR.'
        },
        'dnsx': {
            'name': 'DNSX', 'command_template': 'subfinder -d {target} -silent | dnsx -silent -resp -o {output_file}',
            'phase': PENTEST_PHASES["recon_active"], 'category': 'DNS Resolution & Validation',
            'description': 'Valida y resuelve subdominios (mejor con entrada de subfinder/amass).',
            'needs_shell': True, 'default_enabled': True,
            'depends_on_output_of': 'subfinder' # Conceptual dependency
        },

        # --- 📡 Network Scanning - Ports & Services ---
        'nmap_top_ports': {
            'name': 'Nmap (Top 1000)', 'command_template': 'nmap -sV -T4 --top-ports 1000 {target} -oA {output_file_base}',
            'phase': PENTEST_PHASES["scanning_network"], 'category': 'Port Scanners',
            'description': 'Escaneo de los 1000 puertos TCP más comunes con detección de versión.',
            'default_enabled': True,
            'cli_params': [{'name': 'nmap_extra_args', 'type': 'text', 'label': 'Nmap Extra Arguments', 'placeholder': '-Pn -sC'}]
        },
        'masscan': {
            'name': 'Masscan (Full TCP Scan Example)', 'command_template': 'masscan -p1-65535 {target} --rate 1000 -oJ {output_file_json}',
            'phase': PENTEST_PHASES["scanning_network"], 'category': 'Port Scanners (Fast)',
            'description': 'Escaneo ultrarrápido de todos los puertos TCP (ajustar rate).',
        },
        'naabu': {
            'name': 'Naabu (Top 100)', 'command_template': 'naabu -host {target} -top-ports 100 -silent -o {output_file}',
            'phase': PENTEST_PHASES["scanning_network"], 'category': 'Port Scanners (Fast)',
            'description': 'Escáner simple y rápido de los 100 puertos más comunes.', 'default_enabled': True
        },
        # Netcat, Telnet, SocketStats (ss) are more for manual interaction, harder to fit in automated scans directly for generic reporting.

        # --- 🌐 Web Recon & Fingerprinting ---
        'whatweb': {
            'name': 'WhatWeb', 'command_template': 'whatweb -a 3 {target_url} --log-brief {output_file}',
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'Technology Detection',
            'description': 'Detección de tecnologías web.', 'default_enabled': True, 'target_type': 'url'
        },
        'wappalyzer_cli': {
            'name': 'Wappalyzer CLI', 'command_template': 'wappalyzer {target_url} > {output_file}', # Example, check exact CLI
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'Technology Detection',
            'description': 'Fingerprinting web por línea de comandos.', 'needs_shell': True, 'target_type': 'url'
        },
        'httpx': {
            'name': 'HTTPX (Live & Tech)', 'command_template': 'httpx -silent -status-code -title -tech-detect -o {output_file} -u {target_url_or_domain_list}',
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'HTTP Probe & Info',
            'description': 'Verifica URLs/subdominios, recolecta headers/tech.', 'default_enabled': True, 'target_type': 'url_or_domain_list'
        },
        'aquatone': { # Aquatone and Eyewitness are more for visual recon, output might be many files
            'name': 'Aquatone (Visual Recon)', 'command_template': 'cat {input_file_hosts_or_urls} | aquatone -out {output_directory}',
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'Visual Web Recon',
            'description': 'Captura visual de sitios web (requiere lista de entrada).',
        },
        'eyewitness': {
            'name': 'EyeWitness (Visual Recon)', 'command_template': 'eyewitness --web --threads 5 -f {input_file_urls} -d {output_directory} --no-prompt',
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'Visual Web Recon',
            'description': 'Captura pantallas y metadatos (requiere lista de URLs).',
        },
        'hakrawler': {
            'name': 'Hakrawler', 'command_template': 'hakrawler -url {target_url} -depth 2 -plain > {output_file}',
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'Web Crawling',
            'description': 'Crawler rápido escrito en Go.', 'needs_shell':True, 'target_type': 'url'
        },
        'linkfinder': {
            'name': 'LinkFinder', 'command_template': 'linkfinder -i {target_url_or_js_file} -o cli > {output_file}', # Can take URL or JS file
            'phase': PENTEST_PHASES["web_fingerprint"], 'category': 'JS Link Extraction',
            'description': 'Extrae enlaces JS dinámicamente.', 'needs_shell':True
        },

        # --- 🧪 Web Vulnerability Scanning ---
        'nikto': {
            'name': 'Nikto', 'command_template': 'nikto -h {target_host_or_ip} -o {output_file} -Format txt',
            'phase': PENTEST_PHASES["web_vuln_scan"], 'category': 'Web Server Misconfigurations',
            'description': 'Escáner tradicional de vulnerabilidades web.', 'default_enabled': True, 'target_type': 'host_or_ip'
        },
        'wapiti': {
            'name': 'Wapiti', 'command_template': 'wapiti -u {target_url} -o {output_file_dir} -f txt --scope domain',
            'phase': PENTEST_PHASES["web_vuln_scan"], 'category': 'Black-Box Web App Scan',
            'description': 'Escaneo black-box de aplicaciones web.', 'target_type': 'url'
        },
        # ZAP, Arachni often GUI or complex CLI, Metasploit auxiliary scanners are very specific.

        # --- 🛡️ Infrastructure Vulnerability Scanning --- (Nuclei can fit here too)
        'nuclei': { # Can also be used for web app vulns with different templates
            'name': 'Nuclei (Generic Vulns)', 'command_template': 'nuclei -u {target_url_or_domain_list} -o {output_file} -silent',
            'phase': PENTEST_PHASES["infra_vuln_scan"], 'category': 'Template-based Scanning',
            'description': 'Escáner de vulnerabilidades basado en plantillas (versátil).', 'default_enabled': True, 'target_type': 'url_or_domain_list'
        },

        # --- 📦 CMS & Framework Scanning ---
        'wpscan': {
            'name': 'WPScan', 'command_template': 'wpscan --ignore-main-redirect --url {target_url} --enumerate vp,vt,u --api-token YOUR_WPSCAN_API_TOKEN -o {output_file} -f cli-no-color',
            'phase': PENTEST_PHASES["cms_framework_scan"], 'category': 'WordPress',
            'description': 'Escáner WordPress (requiere API token).', 'requires_api_token': True, 'target_type': 'url',
            'conditional_on': {'tool_id': 'whatweb', 'keyword': 'WordPress'} # Conceptual
        },
        'joomscan': {
            'name': 'JoomScan', 'command_template': 'joomscan --url {target_url} -o {output_file}',
            'phase': PENTEST_PHASES["cms_framework_scan"], 'category': 'Joomla',
            'description': 'Escáner de vulnerabilidades Joomla.', 'target_type': 'url'
        },
        'droopescan': {
            'name': 'Droopescan', 'command_template': 'droopescan scan drupal -u {target_url} -o json > {output_file}',
            'phase': PENTEST_PHASES["cms_framework_scan"], 'category': 'Drupal, SilverStripe, etc.',
            'description': 'Escáner para CMS como Drupal, Joomla, SilverStripe.', 'needs_shell': True, 'target_type': 'url'
        },
        'cmsmap': {
            'name': 'CMSmap', 'command_template': 'cmsmap {target_url} -o {output_file}',
            'phase': PENTEST_PHASES["cms_framework_scan"], 'category': 'Multiple CMS',
            'description': 'Escáner para múltiples CMS (Joomla, WordPress, etc.).', 'target_type': 'url'
        },

        # --- 💣 Fuzzing & Directory Discovery ---
        'ffuf_common': {
            'name': 'FFUF (Common Dirs)', 'command_template': 'ffuf -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -u {target_url}/FUZZ -o {output_file} -of csv -fs 0',
            'phase': PENTEST_PHASES["fuzzing_discovery"], 'category': 'Directory & File Fuzzing',
            'description': 'Fuzzing de directorios y archivos comunes.', 'target_type': 'url'
        },
        'dirb': {
            'name': 'Dirb (Common Dirs)', 'command_template': 'dirb {target_url} /usr/share/wordlists/dirb/common.txt -o {output_file}',
            'phase': PENTEST_PHASES["fuzzing_discovery"], 'category': 'Directory & File Fuzzing',
            'description': 'Escáner de directorios web clásico.', 'target_type': 'url'
        },
        'dirsearch_common': {
            'name': 'Dirsearch (Common Exts)', 'command_template': 'dirsearch -u {target_url} -e php,html,js,txt -w /usr/share/wordlists/dirb/common.txt --output={output_file} --format=simple',
            'phase': PENTEST_PHASES["fuzzing_discovery"], 'category': 'Directory & File Fuzzing',
            'description': 'Búsqueda de directorios y archivos web.', 'target_type': 'url'
        },
        'gobuster_dir': {
            'name': 'Gobuster (Dir Mode)', 'command_template': 'gobuster dir -u {target_url} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -o {output_file}',
            'phase': PENTEST_PHASES["fuzzing_discovery"], 'category': 'Directory & File Fuzzing',
            'description': 'Muy veloz para fuzzing de rutas.', 'target_type': 'url'
        },

        # --- 💥 Exploitation Checks (Automated) ---
        'sqlmap_batch': {
            'name': 'SQLMap (Batch Test)', 'command_template': 'sqlmap -u "{target_url_with_params}" --batch --output-dir={output_file_dir} --results-file=results.txt',
            'phase': PENTEST_PHASES["exploitation_checks"], 'category': 'SQL Injection',
            'description': 'Detección SQLi (modo batch). Intrusivo.', 'dangerous': True, 'target_type': 'url_specific'
        },
        'xsstrike': {
            'name': 'XSStrike (Test)', 'command_template': 'xsstrike -u "{target_url_with_params}" --log-file {output_file} --batch', # Check params
            'phase': PENTEST_PHASES["exploitation_checks"], 'category': 'Cross-Site Scripting (XSS)',
            'description': 'Análisis avanzado de XSS. Intrusivo.', 'dangerous': True, 'target_type': 'url_specific'
        },
        'commix': {
            'name': 'Commix (Test)', 'command_template': 'commix -u "{target_url_with_params}" --batch --output-dir {output_file_dir}', # Check params
            'phase': PENTEST_PHASES["exploitation_checks"], 'category': 'Command Injection',
            'description': 'Explotación de comandos vía inyección. Intrusivo.', 'dangerous': True, 'target_type': 'url_specific'
        },

        # --- 🔐 SSL/TLS Analysis ---
        'sslscan': {
            'name': 'SSLScan (Default)', 'command_template': 'sslscan --no-colour {target_host_or_ip_and_port} > {output_file}',
            'phase': PENTEST_PHASES["tls_ssl_analysis"], 'category': 'SSL/TLS Configuration',
            'description': 'Analiza la configuración SSL/TLS del servidor.', 'needs_shell': True, 'target_type': 'host_or_ip_and_port'
        },
        'testssl_sh': {
            'name': 'TestSSL.sh (Comprehensive)', 'command_template': './testssl.sh --quiet --color 0 -oF {output_file_json} {target_host_or_ip_and_port}', # Assuming testssl.sh is in PATH or current dir
            'phase': PENTEST_PHASES["tls_ssl_analysis"], 'category': 'SSL/TLS Configuration',
            'description': 'Análisis exhaustivo de SSL/TLS.', 'target_type': 'host_or_ip_and_port'
        },

        # --- 🔑 Credential Access - Brute Force ---
        'hydra_ftp': {
            'name': 'Hydra (FTP)', 'command_template': 'hydra -L /usr/share/wordlists/metasploit/unix_users.txt -P /usr/share/wordlists/metasploit/unix_passwords.txt ftp://{target_host_or_ip} -o {output_file}',
            'phase': PENTEST_PHASES["bruteforce_creds"], 'category': 'Brute Force (Network Services)',
            'description': 'Ataque de fuerza bruta a FTP.', 'dangerous': True, 'target_type': 'host_or_ip'
        },
        'hydra_ssh': {
            'name': 'Hydra (SSH)', 'command_template': 'hydra -L /usr/share/wordlists/metasploit/unix_users.txt -P /usr/share/wordlists/metasploit/unix_passwords.txt ssh://{target_host_or_ip} -o {output_file}',
            'phase': PENTEST_PHASES["bruteforce_creds"], 'category': 'Brute Force (Network Services)',
            'description': 'Ataque de fuerza bruta a SSH.', 'dangerous': True, 'target_type': 'host_or_ip'
        },
        'patator_http_basic': {
            'name': 'Patator (HTTP Basic Auth)',
            'command_template': 'patator http_basic_auth host={target_host_or_ip} path=/login user=FILE0 password=FILE1 0=/usr/share/wordlists/dirb/common.txt 1=/usr/share/wordlists/rockyou.txt --output-file {output_file}', # Example, adjust wordlists
            'phase': PENTEST_PHASES["bruteforce_creds"], 'category': 'Brute Force (Web)',
            'description': 'Fuerza bruta a autenticación HTTP básica.', 'dangerous': True, 'target_type': 'host_or_ip'
        }
    }

    # Define Scan Profiles
    scan_profiles = {
        "Light Scan": {
            "description": "Un escaneo rápido con herramientas esenciales para una visión general.",
            "tools": [
                "subfinder", "amass_enum", "dnsx", # Recon
                "nmap_top_ports", "naabu",        # Network Scan
                "whatweb", "httpx",              # Web Fingerprint
                "nikto", "nuclei"                # Web Vuln Scan (generic templates for nuclei)
            ]
        },
        "Deep Scan": {
            "description": "Un escaneo exhaustivo utilizando una gama más amplia de herramientas y técnicas.",
            "tools": [
                # All passive recon
                "subfinder", "assetfinder", "findomain", "whois", "waybackurls", "gau",
                # All active recon
                "amass_enum", "dnsrecon", "dnsx",
                # All network scanning
                "nmap_top_ports", "masscan", "naabu",
                # All web fingerprinting (excluding visual which need input files)
                "whatweb", "wappalyzer_cli", "httpx", "hakrawler", "linkfinder",
                # All web vuln scanning
                "nikto", "wapiti",
                # All infra vuln scanning
                "nuclei",
                # All CMS scanning (excluding those needing API keys if not configured)
                "joomscan", "droopescan", "cmsmap", # wpscan if token available
                # Common fuzzing
                "ffuf_common", "dirb",
                # SSL/TLS
                "sslscan", "testssl_sh"
                # Exploitation and Brute force are generally too intrusive for a default 'deep' scan without explicit consent.
            ]
        }
    }

    return tools_definition, scan_profiles


def get_current_timestamp():
    """Obtiene un timestamp formateado para nombres de archivo/directorio."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def save_job_summary(job_path, job_id, targets, selected_tools, start_time, results_path):
    """Guarda un resumen inicial del job."""
    summary = {
        'job_id': job_id,
        'targets': targets,
        'selected_tools': selected_tools,
        'status': 'running',
        'start_time': start_time.isoformat(),
        'end_time': None,
        'results_path': results_path,
        'tool_progress': {tool: {'status': 'pending', 'output_file': None} for tool in selected_tools},
        'logs': [f"Job {job_id} started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}"]
    }
    summary_file_path = os.path.join(job_path, 'summary.json')
    with open(summary_file_path, 'w') as f:
        json.dump(summary, f, indent=4)
    return summary

def update_job_summary(job_path, update_data):
    """Actualiza el archivo summary.json del job."""
    summary_file_path = os.path.join(job_path, 'summary.json')
    summary = {}
    if os.path.exists(summary_file_path):
        with open(summary_file_path, 'r') as f:
            try:
                summary = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from {summary_file_path}")
                # Potentially create a backup or handle error more gracefully
                summary = {'logs': []} # Fallback to a basic structure
    else:
        # This case should ideally not happen if save_job_summary was called first
        summary = {'logs': []}

    for key, value in update_data.items():
        if key == 'tool_progress': # Merge tool progress dictionaries
            if 'tool_progress' not in summary:
                summary['tool_progress'] = {}
            for tool_id, tool_info in value.items():
                if tool_id not in summary['tool_progress']:
                    summary['tool_progress'][tool_id] = {}
                summary['tool_progress'][tool_id].update(tool_info)
        elif key == 'logs' and isinstance(value, list):
            if 'logs' not in summary:
                summary['logs'] = []
            summary['logs'].extend(value)
        else:
            summary[key] = value

    with open(summary_file_path, 'w') as f:
        json.dump(summary, f, indent=4)


def get_results_zip_path(job_id, results_dir):
    """Devuelve la ruta esperada para el archivo ZIP de resultados de un job."""
    return os.path.join(results_dir, f"{job_id}_results.zip")


def get_target_type_for_tool(tool_config, tool_id):
    """Obtiene el tipo de objetivo esperado por una herramienta."""
    return tool_config.get(tool_id, {}).get('target_type', 'domain_or_ip') # Default a domain/IP


def tool_needs_shell(tool_config, tool_id):
    """Verifica si una herramienta necesita ser ejecutada en un shell."""
    return tool_config.get(tool_id, {}).get('needs_shell', False)


def is_tool_dangerous(tool_config, tool_id):
    """Verifica si una herramienta está marcada como peligrosa/intrusiva."""
    return tool_config.get(tool_id, {}).get('dangerous', False)


def get_tool_cli_params(tool_config, tool_id):
    """Obtiene los parámetros CLI configurables para una herramienta."""
    return tool_config.get(tool_id, {}).get('cli_params', [])


def get_tool_conditional_on(tool_config, tool_id):
    """Obtiene las condiciones para ejecutar una herramienta."""
    return tool_config.get(tool_id, {}).get('conditional_on')


def get_tool_depends_on(tool_config, tool_id):
    """Obtiene las dependencias de salida de una herramienta."""
    return tool_config.get(tool_id, {}).get('depends_on_output_of')


def requires_api_token(tool_config, tool_id):
    """Verifica si una herramienta requiere un API token."""
    return tool_config.get(tool_id, {}).get('requires_api_token', False)