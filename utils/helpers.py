import datetime
import json
import os
import threading # Para el Lock
from pathlib import Path # Añadido para consistencia

jobs_lock = threading.Lock()


PENTEST_PHASES = {
    "reconnaissance_infra_web": {"name": "Reconocimiento (Infraestructura y Web)", "icon_class": "fas fa-eye", "order": 1},
    "identification_infra": {"name": "Identificación (Infraestructura)", "icon_class": "fas fa-server", "order": 2},
    "identification_web": {"name": "Identificación (Aplicaciones Web)", "icon_class": "fas fa-globe-americas", "order": 3},
}

TOOLS_CONFIG = {
    "amass_enum": {
        "id": "amass_enum",
        "name": "Amass Enum",
        "command_template": "amass enum -d {target_domain} -active -ip -brute -min-for-recursive 3 -oA {output_file_base}_amass",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "fas fa-sitemap",
        "icon_class": "fas fa-binoculars",
        "timeout": 1800,
        "default_enabled": True,
        "description": "Descubrimiento profundo de activos y subdominios usando Amass.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -config /path/to/config.ini",
        "dangerous": False,
        "needs_shell": False,
    },
    "subfinder": {
        "id": "subfinder",
        "name": "Subfinder",
        "command_template": "subfinder -d {target_domain} -all -o {output_file}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "fas fa-sitemap",
        "icon_class": "fas fa-search",
        "timeout": 600,
        "default_enabled": True,
        "description": "Descubrimiento pasivo rápido de subdominios.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -t 10 -timeout 30 -sources censys,virustotal",
        "dangerous": False,
        "needs_shell": False,
    },
    "httpx_recon": {
        "id": "httpx_recon",
        "name": "HTTPX (Recon)",
        "command_template": "httpx -l {target_file_subdomains} -silent -title -tech-detect -status-code -o {output_file}",
        "target_type": "domain_list_file",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "fas fa-sitemap",
        "icon_class": "fas fa-project-diagram",
        "timeout": 900,
        "default_enabled": True,
        "description": "Determina hosts web activos y extrae información tecnológica de una lista de subdominios.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -threads 100 -p 80,443,8080",
        "dangerous": False,
        "needs_shell": False,
    },
    "findomain": {
        "id": "findomain",
        "name": "Findomain",
        "command_template": "findomain -t {target_domain} -u {output_file}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "fas fa-sitemap",
        "icon_class": "fas fa-search-dollar",
        "timeout": 600,
        "default_enabled": False,
        "description": "Descubrimiento pasivo de subdominios usando APIs y certificados.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --threads 50 --exclude-sources crtsh",
        "dangerous": False,
        "needs_shell": False,
    },
    "theharvester": {
        "id": "theharvester",
        "name": "theHarvester",
        "command_template": "theHarvester -d {target_domain} -b all -f {output_file_base}_harvester.html",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "fas fa-sitemap",
        "icon_class": "fas fa-user-secret",
        "timeout": 1200,
        "default_enabled": False,
        "description": "OSINT para descubrir subdominios, emails, empleados, IPs.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -l 500 -s",
        "dangerous": False,
        "needs_shell": False,
    },
    "dnsx": {
        "id": "dnsx",
        "name": "DNSX",
        "command_template": "dnsx -l {target_file_subdomains} -silent -a -aaaa -cname -ns -mx -soa -resp -o {output_file}",
        "target_type": "domain_list_file",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-dns",
        "timeout": 600,
        "default_enabled": True,
        "description": "Resolución masiva de DNS y filtrado de registros.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -r /path/to/resolvers.txt -wd example.com",
        "dangerous": False,
        "needs_shell": False,
    },
    "dnsrecon": {
        "id": "dnsrecon",
        "name": "DNSRecon",
        "command_template": "dnsrecon -d {target_domain} -a -s -y -k -w -z -t axfr,std,srv,brt,spf --xml {output_file_xml}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-search-location",
        "timeout": 900,
        "default_enabled": False,
        "description": "Enumeración DNS profunda (AXFR, SRV, etc.).",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --threads 10 -n 8.8.8.8",
        "dangerous": False,
        "needs_shell": False,
    },
    "nmap_dns_scripts": {
        "id": "nmap_dns_scripts",
        "name": "Nmap (DNS Scripts)",
        "command_template": "nmap --script dns-brute,dns-zone-transfer,dns-srv-enum -p 53 {target_domain_or_ip} -oA {output_file_base}_nmap_dns",
        "target_type": "domain_or_ip",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-map-signs",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Scripts NSE de Nmap para interrogación DNS.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --script-args dns-brute.threads=10",
        "dangerous": True,
        "needs_shell": False,
    },
    "massdns": {
        "id": "massdns",
        "name": "MassDNS",
        "command_template": "massdns -r {resolvers_file} -t A -o S -w {output_file} {target_wordlist_file_massdns}",
        "target_type": "domain_wordlist_file",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-fighter-jet",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Fuerza bruta de subdominios a alta velocidad.",
        "cli_params_config": [
            {"name": "resolvers_file", "label": "Archivo de Resolvers", "type": "text", "default": "config/resolvers.txt", "placeholder": "ruta/a/resolvers.txt"},
            {"name": "target_wordlist_file_massdns", "label": "Archivo Wordlist (para MassDNS)", "type": "text", "default": "lists/subdomains-top1million-110000.txt", "placeholder": "ruta/a/wordlist.txt"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -s 10000 --retry 3",
        "dangerous": True,
        "needs_shell": False,
    },
    "nmap_top_ports": {
        "id": "nmap_top_ports",
        "name": "Nmap (Top Ports + Servicios)",
        "command_template": "nmap -sV {nmap_timing_option_value} {nmap_show_open_flag_cmd} --top-ports 1000 {target_host_or_ip} -oA {output_file_base}_nmap_top1000",
        "target_type": "host_or_ip",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-search",
        "timeout": 1200,
        "default_enabled": True,
        "description": "Escaneo Nmap de los 1000 puertos TCP más comunes con detección de servicios.",
        "cli_params_config": [
            {"name": "nmap_timing_option_value", "label": "Timing (-T)", "type": "select", "default": "-T4", "options": ["-T0", "-T1", "-T2", "-T3", "-T4", "-T5"], "description": "Controla la agresividad del escaneo Nmap."},
            {"name": "nmap_show_open_flag_cmd", "label": "Mostrar solo puertos abiertos", "type": "checkbox", "default": False, "cli_true": "--open", "cli_false": "", "description": "Muestra solo los puertos que Nmap determina como abiertos."}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --reason -n -Pn",
        "dangerous": False,
        "needs_shell": False,
    },
    "nmap_full_tcp": {
        "id": "nmap_full_tcp",
        "name": "Nmap (Full TCP + Scripts)",
        "command_template": "nmap -sV -sC -p- {target_host_or_ip} -oA {output_file_base}_nmap_full_tcp",
        "target_type": "host_or_ip",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-search-plus",
        "timeout": 7200,
        "default_enabled": False,
        "description": "Escaneo Nmap completo de todos los puertos TCP, con detección de servicios y scripts por defecto.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -T4 --min-rate 1000",
        "dangerous": True,
        "needs_shell": False,
    },
    "naabu": {
        "id": "naabu",
        "name": "Naabu",
        "command_template": "naabu -host {target_host_or_ip} -pf {ports_to_scan_file} -silent -o {output_file}",
        "target_type": "host_or_ip",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-bolt",
        "timeout": 900,
        "default_enabled": False,
        "description": "Escáner SYN rápido para identificar puertos abiertos.",
        "cli_params_config": [
             {"name": "ports_to_scan_file", "label": "Archivo de Puertos (-pf)", "type": "text", "default": "config/naabu_ports.txt", "placeholder": "ruta/a/ports.txt", "description": "Archivo con puertos a escanear, ej: 80,443,1-1000."}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -rate 1000 -retries 2 -top-ports 100",
        "dangerous": False,
        "needs_shell": False,
    },
    "masscan": {
        "id": "masscan",
        "name": "Masscan",
        "command_template": "masscan -p1-65535 {target_ip_range} --rate={rate} -oL {output_file}",
        "target_type": "ip_range",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "fas fa-network-wired",
        "icon_class": "fas fa-tachometer-alt",
        "timeout": 3600,
        "default_enabled": False,
        "description": "Escáner de puertos extremadamente rápido para grandes rangos IP.",
        "cli_params_config": [
            {"name": "rate", "label": "Tasa de Paquetes (--rate)", "type": "number", "default": 100000, "placeholder": "100000"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --banners --source-port 61000",
        "dangerous": True,
        "needs_shell": False,
    },
    "httpx_tech": {
        "id": "httpx_tech",
        "name": "HTTPX (Tech Detect)",
        "command_template": "httpx -l {target_file_live_hosts} -silent -threads {threads} -tech-detect -server -cdn -waf -o {output_file}",
        "target_type": "url_list_file",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "fas fa-cogs",
        "icon_class": "fas fa-fingerprint",
        "timeout": 900,
        "default_enabled": True,
        "description": "Sondeo de servidores web, detección de tecnología, WAF, CDN desde una lista de hosts.",
        "cli_params_config": [
            {"name": "threads", "label": "Hilos (-threads)", "type": "number", "default": 50, "placeholder": "50"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -x GET,POST -mc 200,302",
        "dangerous": False,
        "needs_shell": False,
    },
    "whatweb": {
        "id": "whatweb",
        "name": "WhatWeb",
        "command_template": "whatweb -a {aggression} {target_url} --log-brief {output_file_json}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "fas fa-cogs",
        "icon_class": "fas fa-microscope",
        "timeout": 300,
        "default_enabled": True,
        "description": "Identificación detallada de tecnologías web, CMS, JavaScript libs.",
        "cli_params_config": [
            {"name": "aggression", "label": "Agresividad (-a)", "type": "select", "default": "3", "options": ["1", "3", "4"], "description": "Nivel de agresividad de WhatWeb."}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --color never --no-errors",
        "dangerous": False,
        "needs_shell": False,
    },
    "nuclei_tech_info": {
        "id": "nuclei_tech_info",
        "name": "Nuclei (Info/Tech)",
        "command_template": "nuclei -u {target_url} -tags info,tech -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "fas fa-cogs",
        "icon_class": "fas fa-info-circle",
        "timeout": 600,
        "default_enabled": True,
        "description": "Usa plantillas de Nuclei para identificar tecnologías y errores de configuración.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -H \"X-Custom-Header: Value\" -retries 3",
        "dangerous": False,
        "needs_shell": False,
    },
    "nmap_http_scripts": {
        "id": "nmap_http_scripts",
        "name": "Nmap (HTTP Scripts)",
        "command_template": "nmap -sV --script http-enum,http-headers,http-waf-fingerprint,http-sitemap-generator -p {ports} {target_ip_or_domain} -oA {output_file_base}_nmap_http",
        "target_type": "ip_or_domain",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "fas fa-cogs",
        "icon_class": "fas fa-file-code",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Scripts HTTP de Nmap para enumerar directorios, WAFs, etc.",
        "cli_params_config": [
            {"name": "ports", "label": "Puertos (-p)", "type": "text", "default": "80,443", "placeholder": "80,443,8080"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --script-args http-enum.fingerprintfile=myprints.lst",
        "dangerous": False,
        "needs_shell": False,
    },
    "ffuf_common": {
        "id": "ffuf_common",
        "name": "FFUF (Common Dirs/Files)",
        "command_template": "ffuf -w {wordlist_path} -u {target_url}/FUZZ {custom_ffuf_headers_cmd} -mc 200,204,301,302,307,401,403 -o {output_file_json} -of json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "fas fa-folder-open",
        "icon_class": "fas fa-search-location",
        "timeout": 1800,
        "default_enabled": True,
        "description": "Fuzzing rápido de directorios y archivos comunes.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "custom_ffuf_headers_cmd", "label": "Cabeceras Adicionales (-H)", "type": "textarea", "default": "", "placeholder": "User-Agent: MiAgente\nCookie: session=123", "description": "Añade cabeceras HTTP personalizadas (una por línea) a las peticiones de FFUF. Formato: Header: Value", "cli_format": "-H \"{value}\""}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -timeout 5 -recursion -recursion-depth 2",
        "dangerous": True,
        "needs_shell": False,
    },
    "dirsearch_common": {
        "id": "dirsearch_common",
        "name": "Dirsearch (Common)",
        "command_template": "dirsearch -u {target_url} -e {extensions} -w {wordlist_path} --output={output_file} --format=json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "fas fa-folder-open",
        "icon_class": "fas fa-folder-tree",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Descubrimiento de rutas y recursos ocultos.",
         "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirb/common.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "extensions", "label": "Extensiones (-e)", "type": "text", "default": "php,html,js,txt", "placeholder": "php,html,js"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --threads 30 --recursive",
        "dangerous": True,
        "needs_shell": False,
    },
     "gobuster_dir": {
        "id": "gobuster_dir",
        "name": "Gobuster (dir)",
        "command_template": "gobuster dir -u {target_url} -w {wordlist_path} -x {extensions} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "fas fa-folder-open",
        "icon_class": "fas fa-ghost",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Fuerza bruta de directorios/archivos.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "extensions", "label": "Extensiones (-x)", "type": "text", "default": "php,txt,html", "placeholder": "php,txt,html"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -t 50 -k --no-error",
        "dangerous": True,
        "needs_shell": False,
    },
    "feroxbuster": {
        "id": "feroxbuster",
        "name": "Feroxbuster",
        "command_template": "feroxbuster --url {target_url} -w {wordlist_path} --depth {depth} -x {extensions} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "fas fa-folder-open",
        "icon_class": "fas fa-rocket",
        "timeout": 2400,
        "default_enabled": False,
        "description": "Descubrimiento recursivo de contenido rápido.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "depth", "label": "Profundidad (--depth)", "type": "number", "default": "3", "placeholder": "3"},
            {"name": "extensions", "label": "Extensiones (-x)", "type": "text", "default": "php,html,js", "placeholder": "php,html,js"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --threads 60 -s 200,301,403",
        "dangerous": True,
        "needs_shell": False,
    },
    "dirb": {
        "id": "dirb",
        "name": "Dirb",
        "command_template": "dirb {target_url} {wordlist_path} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "fas fa-folder-open",
        "icon_class": "fas fa-history",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner clásico de directorios/archivos.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist", "type": "text", "default": "/usr/share/wordlists/dirb/common.txt", "placeholder": "ruta/a/common.txt"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -S -r -z 100",
        "dangerous": True,
        "needs_shell": False,
    },
    "nuclei_vulns": {
        "id": "nuclei_vulns",
        "name": "Nuclei (Vulns Scan)",
        "command_template": "nuclei -u {target_url} -tags {tags} -severity {severity} -o {output_file_json} -json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "fas fa-shield-alt",
        "icon_class": "fas fa-crosshairs",
        "timeout": 1800,
        "default_enabled": True,
        "description": "Escáner basado en plantillas para vulnerabilidades conocidas, CVEs y errores de configuración.",
        "cli_params_config": [
            {"name": "tags", "label": "Tags (-tags)", "type": "text", "default": "cve,security,misconfiguration", "placeholder": "cve,rce"},
            {"name": "severity", "label": "Severidad (-severity)", "type": "text", "default": "critical,high,medium", "placeholder": "critical,high"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -etags ssl -stats",
        "dangerous": False,
        "needs_shell": False,
    },
    "zaproxy_quick": {
        "id": "zaproxy_quick",
        "name": "OWASP ZAP (Quick Scan)",
        "command_template": "zap.sh -cmd -quickurl {target_url} -quickprogress -quickout {output_file_xml}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "fas fa-shield-alt",
        "icon_class": "fas fa-spider",
        "timeout": 3600,
        "default_enabled": False,
        "description": "Escaneo DAST rápido con OWASP ZAP.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -autorun /path/to/script.zst",
        "dangerous": True,
        "needs_shell": True,
    },
    "nikto": {
        "id": "nikto",
        "name": "Nikto",
        "command_template": "nikto -h {target_url} -Format txt -output {output_file} -Tuning {tuning}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "fas fa-shield-alt",
        "icon_class": "fas fa-bug",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner de servidores web para software desactualizado y errores comunes.",
        "cli_params_config": [
            {"name": "tuning", "label": "Tuning (-Tuning)", "type": "text", "default": "x 1,2,3,4,5,b", "placeholder": "x 1,2,3"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -ask no -Plugins tests",
        "dangerous": True,
        "needs_shell": False,
    },
    "wapiti": {
        "id": "wapiti",
        "name": "Wapiti",
        "command_template": "wapiti -u {target_url} -f txt -o {output_file_dir} --scope domain -m {modules_cmd}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "fas fa-shield-alt",
        "icon_class": "fas fa-kiwi-bird",
        "timeout": 2400,
        "default_enabled": False,
        "description": "Escáner de caja negra para XSS, SQLi (detección), etc.",
        "cli_params_config": [
            {"name": "modules_cmd", "label": "Módulos (-m)", "type": "text", "default": "\"-all,+sql,+xss,+crlf,+xxe\"", "placeholder": "\"-all,+sqli,+xss\"", "description": "Módulos a usar, ej: \"-all,+xss\""}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --level 2 -p http://proxy:port",
        "dangerous": True,
        "needs_shell": False, 
    },
    "wpscan": {
        "id": "wpscan",
        "name": "WPScan",
        "command_template": "wpscan --url {target_wordpress_url} --enumerate vp,vt,u {wpscan_api_token_cmd} -o {output_file} -f cli-no-color --disable-tls-checks",
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "fas fa-puzzle-piece",
        "icon_class": "fab fa-wordpress",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Escáner de vulnerabilidades para WordPress.",
        "cli_params_config": [
            {"name": "wpscan_api_token_cmd", "label": "API Token WPScan", "type": "text", "default": "", "placeholder": "TU_API_TOKEN_WPSCAN", "description": "Token API de wpscan.com para detección de vulnerabilidades actualizada. Si se deja vacío, no se usará el flag --api-token."}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --random-user-agent --plugins-detection aggressive",
        "dangerous": False,
        "needs_shell": False,
    },
    "joomscan": {
        "id": "joomscan",
        "name": "JoomScan",
        "command_template": "joomscan --url {target_joomla_url} -ec -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "fas fa-puzzle-piece",
        "icon_class": "fab fa-joomla",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner de vulnerabilidades para Joomla CMS.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --enumerate-components --cookie \"test=123\"",
        "dangerous": False,
        "needs_shell": False,
    },
    "droopescan": {
        "id": "droopescan",
        "name": "Droopescan",
        "command_template": "droopescan scan -u {target_url} -t {threads} -o cli > {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "fas fa-puzzle-piece",
        "icon_class": "fab fa-drupal",
        "timeout": 900,
        "default_enabled": False,
        "description": "Identifica múltiples CMS (Drupal, Silverstripe, Joomla, WordPress) y enumera componentes.",
        "cli_params_config": [
            {"name": "threads", "label": "Hilos (-t)", "type": "number", "default": 32, "placeholder": "32"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -e a",
        "dangerous": False,
        "needs_shell": True,
    },
    "cmsmap": {
        "id": "cmsmap",
        "name": "CMSmap",
        "command_template": "cmsmap {target_url} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "fas fa-puzzle-piece",
        "icon_class": "fas fa-cogs",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Identifica CMS y ejecuta comprobaciones básicas de vulnerabilidades.",
        "cli_params_config": [],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -f D -F --user-agent MyAgent",
        "dangerous": False,
        "needs_shell": False,
    },
    "sqlmap_batch": {
        "id": "sqlmap_batch",
        "name": "SQLMap (Detection)",
        "command_template": "sqlmap -u \"{target_url_with_params}\" --batch --level={level} --risk={risk} --technique=BEUSTQ --forms --crawl={crawl_depth} --output-dir={output_file_dir_sqlmap}",
        "target_type": "url_with_params",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "fas fa-bomb",
        "icon_class": "fas fa-database",
        "timeout": 3600,
        "default_enabled": False,
        "description": "Detección de inyección SQL (sin explotación).",
        "cli_params_config": [
            {"name": "level", "label": "Nivel (--level)", "type": "select", "default": "3", "options": ["1","2","3","4","5"]},
            {"name": "risk", "label": "Riesgo (--risk)", "type": "select", "default": "1", "options": ["1","2","3"]},
            {"name": "crawl_depth", "label": "Profundidad Crawl (--crawl)", "type": "number", "default": "2", "placeholder": "2"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --dbms=mysql --threads=5 -o",
        "needs_shell": False,
        "dangerous": True,
    },
    "nuclei_specific_vulns": {
        "id": "nuclei_specific_vulns",
        "name": "Nuclei (Specific Vulns)",
        "command_template": "nuclei -u {target_url} -t {nuclei_templates} -o {output_file_json} -json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "fas fa-bomb",
        "icon_class": "fas fa-bullseye",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de clases específicas de vulnerabilidades (SSRF, SSTI, LFI, etc.) con plantillas Nuclei.",
        "cli_params_config": [
            {"name": "nuclei_templates", "label": "Plantillas (-t)", "type": "text", "default": "http/misconfiguration/,http/vulnerabilities/", "placeholder": "ruta/a/plantillas/,http/cves/"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: -pt http -timeout 10",
        "dangerous": False,
        "needs_shell": False,
    },
    "commix": {
        "id": "commix",
        "name": "Commix (Command Inj. Detection)",
        "command_template": "commix -u \"{target_url_with_params}\" --batch --level={level} -o {output_file}",
        "target_type": "url_with_params",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "fas fa-bomb",
        "icon_class": "fas fa-terminal",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de inyección de comandos.",
        "cli_params_config": [
            {"name": "level", "label": "Nivel (--level)", "type": "select", "default": "3", "options": ["1","2","3","4","5"]}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --os=linux --technique=time",
        "dangerous": True,
        "needs_shell": False,
    },
    "xsser": {
        "id": "xsser",
        "name": "XSSer (XSS Detection)",
        "command_template": "xsser -u \"{target_url}\" {xsser_params_cmd} -Cw --heuristic --user-agent \"Mozilla/5.0\" -o {output_file_xml}",
        "target_type": "url_and_params",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "fas fa-bomb",
        "icon_class": "fas fa-code",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de Cross-Site Scripting (XSS).",
        "cli_params_config": [
            {"name": "xsser_params_cmd", "label": "Parámetros URL (--params)", "type": "text", "default": "", "placeholder": "param1=val1&param2=val2", "description": "Parámetros a probar para XSS, ej: q=FUZZ&category=test. Si está vacío, no se pasará --params."}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --payload \"<script>alert(1)</script>\"",
        "dangerous": True,
        "needs_shell": False,
    },
    "lfisuite_scan": {
        "id": "lfisuite_scan",
        "name": "LFISuite (LFI/RFI Scan)",
        "command_template": "lfisuite -u \"{target_url_with_lfi_fuzz_param}\" --scan -w {lfi_wordlist} -o {output_file_dir}",
        "target_type": "url_with_lfi_fuzz_param",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "fas fa-bomb",
        "icon_class": "fas fa-file-import",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de vulnerabilidades de Inclusión Local y Remota de Archivos (LFI/RFI).",
        "cli_params_config": [
            {"name": "lfi_wordlist", "label": "Wordlist LFI (-w)", "type": "text", "default": "/usr/share/seclists/Fuzzing/LFI/LFI-Jhaddix.txt", "placeholder": "ruta/a/lfi_wordlist.txt"}
        ],
        "allow_additional_args": True,
        "additional_args_placeholder": "ej: --threads 10 --skip-urlencode",
        "dangerous": True,
        "needs_shell": False,
    },
}


PROFILES_CONFIG = {
    "Full Recon (Domain)": {
        "description": "Reconocimiento exhaustivo de un dominio (subdominios, DNS, OSINT).",
        "icon_class": "fas fa-search-plus",
        "tools": ["amass_enum", "subfinder", "findomain", "theharvester", "dnsrecon", "nmap_dns_scripts"],
        "params_override": {
            "amass_enum": {"min-for-recursive": "2"}, 
        }
    },
    "Quick Web Scan (URL)": {
        "description": "Escaneo web rápido de un URL (tecnologías, directorios comunes, vulnerabilidades básicas).",
        "icon_class": "fas fa-bolt",
        "tools": ["httpx_tech", "whatweb", "ffuf_common", "nuclei_tech_info", "nuclei_vulns"],
         "params_override": {
            "ffuf_common": {"wordlist_path": "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt"}
        }
    },
    "Infrastructure Scan (IP/Host)": {
        "description": "Escaneo de infraestructura en un IP o Host (puertos comunes, servicios).",
        "icon_class": "fas fa-network-wired",
        "tools": ["nmap_top_ports", "naabu"],
        "params_override": {}
    },
    "CMS Scan (WordPress URL)": {
        "description": "Escaneo específico para un sitio WordPress.",
        "icon_class": "fab fa-wordpress",
        "tools": ["wpscan", "whatweb", "nuclei_vulns"],
        "params_override": {
            "nuclei_vulns": {"tags": "wordpress,cve,misconfiguration"}
        }
    }
}


TARGET_PLACEHOLDERS_MAP = {
    "{target}": "target_value",  # Valor genérico del target
    "{target_domain}": "target_value",
    "{target_url}": "target_value",
    "{target_host_or_ip}": "target_value",
    "{target_ip_range}": "target_value",
    "{target_domain_or_ip}": "target_value",
    "{target_wordpress_url}": "target_value",
    "{target_joomla_url}": "target_value",
    "{target_url_with_params}": "target_value", # El usuario debe proveer la URL completa con params
    "{target_url_with_lfi_fuzz_param}": "target_value", # El usuario debe proveer la URL con FUZZ
    "{target_file_subdomains}": "initial_targets_file_path",
    "{target_file_live_hosts}": "initial_targets_file_path", # Podría ser diferente si generas otro archivo
    "{target_wordlist_file_massdns}": "initial_targets_file_path" # Para MassDNS si usa la lista de targets inicial
}

OUTPUT_PLACEHOLDERS_LIST = [
    "{output_file}",
    "{output_file_base}",
    "{output_file_json}",
    "{output_file_xml}",
    "{output_file_dir}",
    "{output_file_dir_sqlmap}" # Añadido si lo usas
]



def get_tools_definition():
    """Devuelve la configuración de herramientas, asegurando que cada una tenga un ID."""
    for tool_id, config in TOOLS_CONFIG.items():
        config['id'] = tool_id
    return TOOLS_CONFIG

def get_scan_profiles():
    """Devuelve la configuración de perfiles de escaneo."""
    return PROFILES_CONFIG

def get_pentest_phases():
    """Devuelve la configuración de las fases de pentesting."""
    return PENTEST_PHASES

def get_tool_config():
    """
    Devuelve la configuración de herramientas y perfiles en un formato específico
    compatible con el scanner/engine.py original si aún se usa.
    """
    return {
        "raw_commands": get_tools_definition(), 
        "presets": get_scan_profiles()   
    }


def get_current_timestamp():
    """Devuelve el timestamp actual en formato ISO."""
    return datetime.datetime.now().isoformat()

def get_current_timestamp_str():
    """Devuelve un timestamp actual como string formateado para nombres de archivo/IDs."""
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')

def create_job_directories(base_path: str, job_id: str) -> str:
    """
    Crea la estructura de directorios para un nuevo job.
    Args:
        base_path: Directorio base donde se crearán los directorios de jobs (ej. app.config["RESULTS_DIR"])
        job_id: Identificador único del job.
    Returns:
        Ruta al directorio del job creado.
    """
    job_path_obj = Path(base_path) / job_id
    job_path_obj.mkdir(parents=True, exist_ok=True)
    (job_path_obj / 'tool_outputs').mkdir(exist_ok=True)
    return str(job_path_obj)


def save_job_summary(job_path: str, summary_data_to_save: dict):
    """
    Guarda o actualiza el archivo summary.json del job.
    Args:
        job_path: Ruta al directorio del job.
        summary_data_to_save: Diccionario con los datos del job a guardar/actualizar.
    """
    summary_file_path = Path(job_path) / 'summary.json'
    
    current_summary_on_disk = {}
    if summary_file_path.exists():
        try:
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                current_summary_on_disk = json.load(f)
        except json.JSONDecodeError:
            job_id_for_log = Path(job_path).name
            print(f"WARN: summary.json en {job_path} (Job ID: {job_id_for_log}) corrupto. Se sobrescribirá.")
        except IOError as e:
            job_id_for_log = Path(job_path).name
            print(f"WARN: No se pudo leer summary.json en {job_path} (Job ID: {job_id_for_log}): {e}. Se intentará sobrescribir.")

    for key, value in summary_data_to_save.items():
        current_summary_on_disk[key] = value
            
    current_summary_on_disk.setdefault('job_id', Path(job_path).name)
    current_summary_on_disk.setdefault('status', 'UNKNOWN')
    current_summary_on_disk.setdefault('overall_progress', 0)
    current_summary_on_disk.setdefault('logs', [])
    current_summary_on_disk.setdefault('tool_progress', {})

    try:
        with open(summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(current_summary_on_disk, f, indent=4)
    except IOError as e:
        job_id_log = current_summary_on_disk.get('job_id', Path(job_path).name)
        print(f"ERROR: No se pudo escribir/actualizar summary.json para job {job_id_log}: {e}")


def get_scan_status_from_file(job_path: str) -> dict:
    """
    Obtiene el estado de un escaneo leyendo directamente del archivo summary.json.
    Args:
        job_path: Ruta completa al directorio del job que contiene summary.json
    Returns:
        Diccionario con los datos del escaneo o estructura de error si falla
    """
    summary_file_path = Path(job_path) / 'summary.json'
    job_id_from_path = Path(job_path).name 

    if summary_file_path.exists():
        try:
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            summary_data.setdefault('job_id', job_id_from_path)
            summary_data.setdefault('status', 'UNKNOWN')
            summary_data.setdefault('overall_progress', 0)
            summary_data.setdefault('logs', [])
            summary_data.setdefault('tool_progress', {})
            summary_data.setdefault('targets', [])
            summary_data.setdefault('start_timestamp', None) 
            summary_data.setdefault('creation_timestamp', None) 
            summary_data.setdefault('end_timestamp', None) 
            summary_data.setdefault('zip_path', None)
            summary_data.setdefault('error_message', None)
            return summary_data
        except (IOError, json.JSONDecodeError) as e:
            print(f"WARN: No se pudo leer o decodificar summary.json en {job_path} (Job ID: {job_id_from_path}): {e}")
    
    return {
        'job_id': job_id_from_path,
        'status': 'NOT_FOUND', 
        'error_message': 'summary.json no encontrado o corrupto.',
        'overall_progress': 0,
        'logs': [{'timestamp': get_current_timestamp(), 'level': 'error', 'message': 'summary.json no encontrado o corrupto.', 'is_html': False}],
        'tool_progress': {},
        'targets': [],
        'start_timestamp': None,
        'creation_timestamp': None,
        'end_timestamp': None,
        'zip_path': None,
    }


def list_all_jobs(job_path_base: str) -> list:
    """
    Lista todos los jobs disponibles en el directorio base leyendo sus summary.json.
    Args:
        job_path_base: Directorio raíz donde se guardan los jobs
    Returns:
        Lista de diccionarios con información básica de cada job
    """
    jobs = []
    base = Path(job_path_base)
    if base.exists() and base.is_dir():
        for job_dir in base.iterdir():
            if job_dir.is_dir() and (job_dir / 'summary.json').exists():
                job_summary = get_scan_status_from_file(str(job_dir))
                jobs.append({
                    'id': job_summary.get('job_id', job_dir.name),
                    'status': job_summary.get('status', 'UNKNOWN'),
                    'timestamp': job_summary.get('start_timestamp') or job_summary.get('creation_timestamp'),
                    'targets': job_summary.get('targets', []),
                    'zip_path': job_summary.get('zip_path')
                })
    return sorted(jobs, key=lambda j: j.get('timestamp') or '0', reverse=True)

def load_tools_config(config_path_str=None):
    """Carga la configuración de herramientas. Prioriza archivo, luego variable global."""
    if config_path_str:
        config_path = Path(config_path_str)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    for tool_id, config_data in loaded_config.items():
                        config_data['id'] = tool_id
                    return loaded_config
            except Exception as e:
                print(f"Error al cargar la configuración de herramientas desde {config_path}: {e}. Usando configuración interna.")
        else:
            print(f"Advertencia: Archivo de configuración de herramientas no encontrado en {config_path}. Usando configuración interna.")
    
    print(f"Advertencia: Usando configuración de herramientas interna (TOOLS_CONFIG).")
    return get_tools_definition()

def load_profiles_config(config_path_str=None):
    """Carga los perfiles de escaneo. Usa PROFILES_CONFIG como fallback."""
    if config_path_str:
        config_path = Path(config_path_str)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error al cargar la configuración de perfiles desde {config_path}: {e}. Usando configuración interna.")

    print(f"Advertencia: Usando configuración de perfiles interna (PROFILES_CONFIG).")
    return get_scan_profiles()

SCAN_PHASES = PENTEST_PHASES 

def generate_job_id():
    """Genera un ID de trabajo único basado en el timestamp."""
    return f"scan_{get_current_timestamp_str()}"