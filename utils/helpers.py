import datetime
import json
import os
import threading # Para el Lock
from pathlib import Path # Añadido para consistencia

jobs_lock = threading.Lock()


PENTEST_PHASES = {
    "reconnaissance_infra_web": {"name": "Reconocimiento (Infraestructura y Web)", "icon_class": "icon-eye", "order": 1},
    "identification_infra": {"name": "Identificación (Infraestructura)", "icon_class": "icon-server", "order": 2},
    "identification_web": {"name": "Identificación (Aplicaciones Web)", "icon_class": "icon-globe-search", "order": 3},
}

TOOLS_CONFIG = {
    "amass_enum": {
        "name": "Amass Enum",
        "command_template": "amass enum -d {target_domain} -active -ip -brute -min-for-recursive 3 -oA {output_file_base}_amass",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "icon-sitemap",
        "icon_class": "icon-binoculars",
        "timeout": 1800, # 30 minutos
        "default_enabled": True,
        "description": "Descubrimiento profundo de activos y subdominios usando Amass.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "subfinder": {
        "name": "Subfinder",
        "command_template": "subfinder -d {target_domain} -all -o {output_file}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "icon-sitemap",
        "icon_class": "icon-search",
        "timeout": 600, # 10 minutos
        "default_enabled": True,
        "description": "Descubrimiento pasivo rápido de subdominios.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "httpx_recon": { # Renombrado para evitar colisión con httpx_tech
        "name": "HTTPX (Recon)",
        "command_template": "httpx -l {target_file_subdomains} -silent -title -tech-detect -status-code -o {output_file}",
        "target_type": "domain_list_file", # Tipo especial para indicar que necesita un archivo de entrada
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "icon-sitemap",
        "icon_class": "icon-http",
        "timeout": 900, # 15 minutos
        "default_enabled": True,
        "description": "Determina hosts web activos y extrae información tecnológica.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False, # httpx puede necesitar shell si se usa con pipes `cat ... | httpx`
    },
    "findomain": {
        "name": "Findomain",
        "command_template": "findomain -t {target_domain} -u {output_file}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "icon-sitemap",
        "icon_class": "icon-search-dollar",
        "timeout": 600, # 10 minutos
        "default_enabled": False,
        "description": "Descubrimiento pasivo de subdominios usando APIs y certificados.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "theharvester": {
        "name": "theHarvester",
        "command_template": "theHarvester -d {target_domain} -b all -f {output_file_base}_harvester.html", # Salida HTML
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "Asset Discovery",
        "category_display_name": "Descubrimiento de Activos y Subdominios",
        "category_icon_class": "icon-sitemap",
        "icon_class": "icon-user-secret",
        "timeout": 1200, # 20 minutos
        "default_enabled": False,
        "description": "OSINT para descubrir subdominios, emails, empleados, IPs.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "dnsx": {
        "name": "DNSX",
        "command_template": "dnsx -l {target_file_subdomains} -silent -a -aaaa -cname -ns -mx -soa -resp -o {output_file}",
        "target_type": "domain_list_file",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-dns",
        "timeout": 600,
        "default_enabled": True,
        "description": "Resolución masiva de DNS y filtrado de registros.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "dnsrecon": {
        "name": "DNSRecon",
        "command_template": "dnsrecon -d {target_domain} -a -s -y -k -w -z -t axfr,std,srv,brt,spf --xml {output_file_xml}",
        "target_type": "domain",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-search-location",
        "timeout": 900,
        "default_enabled": False,
        "description": "Enumeración DNS profunda (AXFR, SRV, etc.).",
        "cli_params_config": [],
        "dangerous": False, # AXFR puede ser ruidoso
        "needs_shell": False,
    },
    "nmap_dns_scripts": {
        "name": "Nmap (DNS Scripts)",
        "command_template": "nmap --script dns-brute,dns-zone-transfer,dns-srv-enum -p 53 {target_domain_or_ip} -oA {output_file_base}_nmap_dns",
        "target_type": "domain_or_ip",
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-map-signs",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Scripts NSE de Nmap para interrogación DNS.",
        "cli_params_config": [],
        "dangerous": True, # dns-brute puede ser ruidoso
        "needs_shell": False,
    },
    "massdns": {
        "name": "MassDNS",
        "command_template": "massdns -r {resolvers_file} -t A -o S -w {output_file} {target_wordlist_file}",
        "target_type": "domain_wordlist_file", # Tipo especial
        "phase": "reconnaissance_infra_web",
        "category": "DNS Enumeration",
        "category_display_name": "Enumeración DNS Avanzada",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-fighter-jet",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Fuerza bruta de subdominios a alta velocidad.",
        "cli_params_config": [
            {"name": "resolvers_file", "label": "Archivo de Resolvers", "type": "text", "default": "lists/resolvers.txt", "placeholder": "ruta/a/resolvers.txt"},
            {"name": "wordlist_file", "label": "Archivo Wordlist (para {target})", "type": "text", "default": "lists/default_sub_wordlist.txt", "placeholder": "ruta/a/wordlist.txt"}
        ],
        "dangerous": True, # Puede generar mucho tráfico DNS
        "needs_shell": False,
    },

    "nmap_top_ports": {
        "name": "Nmap (Top Ports + Servicios)",
        "command_template": "nmap -sV {nmap_timing_option} --top-ports 1000 {target_host_or_ip} -oA {output_file_base}_nmap_top1000",
        "target_type": "host_or_ip",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-search",
        "timeout": 1200, # 20 minutos
        "default_enabled": True,
        "description": "Escaneo Nmap de los 1000 puertos TCP más comunes con detección de servicios.",
        "cli_params_config": [
            {"name": "nmap_timing_option", "label": "Timing (-T)", "type": "select", "default": "-T4", "options": ["-T0", "-T1", "-T2", "-T3", "-T4", "-T5"], "description": "Controla la agresividad del escaneo Nmap."}
        ],
        "dangerous": False, # Relativamente estándar
        "needs_shell": False,
    },
    "nmap_full_tcp": {
        "name": "Nmap (Full TCP + Scripts)",
        "command_template": "nmap -sV -sC -p- {target_host_or_ip} -oA {output_file_base}_nmap_full_tcp",
        "target_type": "host_or_ip",
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-search-plus",
        "timeout": 7200, # 2 horas (puede ser largo)
        "default_enabled": False,
        "description": "Escaneo Nmap completo de todos los puertos TCP, con detección de servicios y scripts por defecto.",
        "cli_params_config": [],
        "dangerous": True, # Intrusivo y lento
        "needs_shell": False,
    },
    "naabu": {
        "name": "Naabu",
        "command_template": "naabu -host {target_host_or_ip_list} -pf {ports_to_scan_file} -silent -o {output_file}",
        "target_type": "host_or_ip", # Simplificado a un solo host, o se necesita lógica para listas
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-bolt",
        "timeout": 900, # 15 minutos
        "default_enabled": False,
        "description": "Escáner SYN rápido para identificar puertos abiertos.",
        "cli_params_config": [
             {"name": "ports_to_scan_file", "label": "Archivo de Puertos", "type": "text", "default": "config/naabu_ports.txt", "placeholder": "ruta/a/ports.txt", "description": "Archivo con puertos a escanear, ej: 80,443,1-1000."}
        ],
        "dangerous": False, # Escaneo SYN es sigiloso
        "needs_shell": False,
    },
    "masscan": {
        "name": "Masscan",
        "command_template": "masscan -p1-65535 {target_ip_range} --rate=100000 -oL {output_file}",
        "target_type": "ip_range", # e.g., 192.168.1.0/24
        "phase": "identification_infra",
        "category": "Port Scanning",
        "category_display_name": "Escaneo de Puertos",
        "category_icon_class": "icon-network-wired",
        "icon_class": "icon-tachometer-alt",
        "timeout": 3600, # 1 hora
        "default_enabled": False,
        "description": "Escáner de puertos extremadamente rápido para grandes rangos IP.",
        "cli_params_config": [
            {"name": "rate", "label": "Tasa de Paquetes", "type": "number", "default": "100000", "placeholder": "100000"}
        ],
        "dangerous": True, # Muy ruidoso y puede causar problemas de red
        "needs_shell": False,
    },

    "httpx_tech": {
        "name": "HTTPX (Tech Detect)",
        "command_template": "httpx -l {target_file_live_hosts} -silent -threads 50 -tech-detect -server -cdn -waf -o {output_file}",
        "target_type": "url_list_file", # Requiere un archivo de hosts web vivos
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "icon-cogs",
        "icon_class": "icon-fingerprint",
        "timeout": 900,
        "default_enabled": True,
        "description": "Sondeo de servidores web, detección de tecnología, WAF, CDN.",
        "cli_params_config": [
            {"name": "threads", "label": "Hilos (-threads)", "type": "number", "default": "50", "placeholder": "50"}
        ],
        "dangerous": False,
        "needs_shell": False, # Similar a httpx_recon
    },
    "whatweb": { # Renombrado de whatweb_basic para evitar confusión
        "name": "WhatWeb",
        "command_template": "whatweb -a 3 {target_url} --log-brief {output_file_json}", # Salida JSON
        "target_type": "url",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "icon-cogs",
        "icon_class": "icon-microscope",
        "timeout": 300,
        "default_enabled": True,
        "description": "Identificación detallada de tecnologías web, CMS, JavaScript libs.",
        "cli_params_config": [
            {"name": "aggression", "label": "Agresividad (-a)", "type": "select", "default": "3", "options": ["1", "3", "4"], "description": "Nivel de agresividad de WhatWeb."}
        ],
        "dangerous": False, # Puede ser algo ruidoso con -a 3/4
        "needs_shell": False,
    },
    "nuclei_tech_info": {
        "name": "Nuclei (Info/Tech)",
        "command_template": "nuclei -u {target_url} -tags info,tech -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "icon-cogs",
        "icon_class": "icon-info-circle",
        "timeout": 600,
        "default_enabled": True,
        "description": "Usa plantillas de Nuclei para identificar tecnologías y errores de configuración.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "nmap_http_scripts": {
        "name": "Nmap (HTTP Scripts)",
        "command_template": "nmap -sV --script http-enum,http-headers,http-waf-fingerprint,http-sitemap-generator -p 80,443 {target_ip_or_domain} -oA {output_file_base}_nmap_http",
        "target_type": "ip_or_domain",
        "phase": "identification_web",
        "category": "Web Tech Identification",
        "category_display_name": "Identificación de Tecnologías Web",
        "category_icon_class": "icon-cogs",
        "icon_class": "icon-file-code",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Scripts HTTP de Nmap para enumerar directorios, WAFs, etc.",
        "cli_params_config": [
            {"name": "ports", "label": "Puertos (-p)", "type": "text", "default": "80,443", "placeholder": "80,443,8080"}
        ],
        "dangerous": False, # Puede ser un poco ruidoso
        "needs_shell": False,
    },

    "ffuf_common": {
        "name": "FFUF (Common Dirs/Files)",
        "command_template": "ffuf -w {wordlist_path} -u {target_url}/FUZZ -mc 200,204,301,302,307,401,403 -o {output_file_json} -of json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "icon-folder-open",
        "icon_class": "icon-search-location",
        "timeout": 1800,
        "default_enabled": True,
        "description": "Fuzzing rápido de directorios y archivos comunes.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"}
        ],
        "dangerous": True, # Genera mucho tráfico
        "needs_shell": False,
    },
    "dirsearch_common": {
        "name": "Dirsearch (Common)",
        "command_template": "dirsearch -u {target_url} -e php,html,js,txt,asp,aspx,jsp -w {wordlist_path} --output={output_file} --format=json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "icon-folder-open",
        "icon_class": "icon-folder-tree",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Descubrimiento de rutas y recursos ocultos.",
         "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist", "type": "text", "default": "/usr/share/wordlists/dirb/common.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "extensions", "label": "Extensiones (-e)", "type": "text", "default": "php,html,js,txt", "placeholder": "php,html,js"}
        ],
        "dangerous": True,
        "needs_shell": False,
    },
     "gobuster_dir": {
        "name": "Gobuster (dir)",
        "command_template": "gobuster dir -u {target_url} -w {wordlist_path} -x php,txt,html -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "icon-folder-open",
        "icon_class": "icon-ghost",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Fuerza bruta de directorios/archivos.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "extensions", "label": "Extensiones (-x)", "type": "text", "default": "php,txt,html", "placeholder": "php,txt,html"}
        ],
        "dangerous": True,
        "needs_shell": False,
    },
    "feroxbuster": {
        "name": "Feroxbuster",
        "command_template": "feroxbuster -u {target_url} -w {wordlist_path} --depth 3 -x php,html,js -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "icon-folder-open",
        "icon_class": "icon-rocket",
        "timeout": 2400, # Puede ser más largo con recursión
        "default_enabled": False,
        "description": "Descubrimiento recursivo de contenido rápido.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist (-w)", "type": "text", "default": "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt", "placeholder": "ruta/a/wordlist.txt"},
            {"name": "depth", "label": "Profundidad (--depth)", "type": "number", "default": "3", "placeholder": "3"},
            {"name": "extensions", "label": "Extensiones (-x)", "type": "text", "default": "php,html,js", "placeholder": "php,html,js"}
        ],
        "dangerous": True,
        "needs_shell": False,
    },
    "dirb": {
        "name": "Dirb",
        "command_template": "dirb {target_url} {wordlist_path} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Content Discovery",
        "category_display_name": "Descubrimiento de Contenido",
        "category_icon_class": "icon-folder-open",
        "icon_class": "icon-history",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner clásico de directorios/archivos.",
        "cli_params_config": [
            {"name": "wordlist_path", "label": "Wordlist", "type": "text", "default": "/usr/share/wordlists/dirb/common.txt", "placeholder": "ruta/a/common.txt"}
        ],
        "dangerous": True,
        "needs_shell": False,
    },

    "nuclei_vulns": {
        "name": "Nuclei (Vulns Scan)",
        "command_template": "nuclei -u {target_url} -tags cve,security,misconfiguration -severity critical,high,medium -o {output_file_json} -json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "icon-shield-alt",
        "icon_class": "icon-crosshairs",
        "timeout": 1800,
        "default_enabled": True,
        "description": "Escáner basado en plantillas para vulnerabilidades conocidas, CVEs y errores de configuración.",
        "cli_params_config": [
            {"name": "tags", "label": "Tags (-tags)", "type": "text", "default": "cve,security,misconfiguration", "placeholder": "cve,rce"},
            {"name": "severity", "label": "Severidad (-severity)", "type": "text", "default": "critical,high,medium", "placeholder": "critical,high"}
        ],
        "dangerous": False, # Mayormente no intrusivo, pero depende de las plantillas
        "needs_shell": False,
    },
    "zaproxy_quick": { # OWASP ZAP
        "name": "OWASP ZAP (Quick Scan)",
        "command_template": "zap.sh -cmd -quickurl {target_url} -quickprogress -quickout {output_file_xml}", # Asume zap.sh en PATH
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "icon-shield-alt",
        "icon_class": "icon-spider",
        "timeout": 3600, # Puede ser largo
        "default_enabled": False,
        "description": "Escaneo DAST rápido con OWASP ZAP.",
        "cli_params_config": [],
        "dangerous": True, # Escaneo activo DAST
        "needs_shell": True, # zap.sh es un script
    },
    "nikto": {
        "name": "Nikto",
        "command_template": "nikto -h {target_url} -Format txt -output {output_file} -Tuning x 1,2,3,4,5,b",
        "target_type": "url", # Nikto puede tomar host, pero url es más común para -h
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "icon-shield-alt",
        "icon_class": "icon-bug",
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner de servidores web para software desactualizado y errores comunes.",
        "cli_params_config": [
            {"name": "tuning", "label": "Tuning (-Tuning)", "type": "text", "default": "x 1,2,3,4,5,b", "placeholder": "x 1,2,3"}
        ],
        "dangerous": True, # Puede ser ruidoso
        "needs_shell": False,
    },
    "wapiti": {
        "name": "Wapiti",
        "command_template": "wapiti -u {target_url} -f txt -o {output_file_dir} --scope domain -m \"-all,+sql,+xss,+crlf,+xxe\"",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Automated Vuln Analysis",
        "category_display_name": "Análisis Automatizado de Vulnerabilidades",
        "category_icon_class": "icon-shield-alt",
        "icon_class": "icon-kiwi-bird", # Wapiti es un ave :)
        "timeout": 2400,
        "default_enabled": False,
        "description": "Escáner de caja negra para XSS, SQLi (detección), etc.",
        "cli_params_config": [
            {"name": "modules", "label": "Módulos (-m)", "type": "text", "default": "\"-all,+sql,+xss,+crlf,+xxe\"", "placeholder": "\"-all,+sqli,+xss\""}
        ],
        "dangerous": True, # Escaneo activo
        "needs_shell": False, # Wapiti es un ejecutable Python, pero el comando puede tener comillas
    },

    "wpscan": {
        "name": "WPScan",
        "command_template": "wpscan --url {target_wordpress_url} --enumerate vp,vt,u --api-token {wpscan_api_token} -o {output_file} -f cli-no-color --disable-tls-checks", # Añadido disable-tls-checks por si acaso
        "target_type": "url", # Específicamente URL de WordPress
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "icon-puzzle-piece",
        "icon_class": "icon-wordpress",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Escáner de vulnerabilidades para WordPress.",
        "cli_params_config": [
            {"name": "wpscan_api_token", "label": "API Token WPScan", "type": "password", "default": "", "placeholder": "TU_API_TOKEN_WPSCAN", "description": "Token API de wpscan.com para detección de vulnerabilidades actualizada."}
        ],
        "dangerous": False, # Enumeración, pero puede ser detectado
        "needs_shell": False,
    },
    "joomscan": {
        "name": "JoomScan",
        "command_template": "joomscan --url {target_joomla_url} -ec -o {output_file}",
        "target_type": "url", # Específicamente URL de Joomla
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "icon-puzzle-piece",
        "icon_class": "icon-joomla", # Asumiendo que tienes un ícono para Joomla
        "timeout": 1200,
        "default_enabled": False,
        "description": "Escáner de vulnerabilidades para Joomla CMS.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },
    "droopescan": {
        "name": "Droopescan",
        "command_template": "droopescan scan -u {target_url} -t 32 -o cli > {output_file}", # Redirigir salida cli
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "icon-puzzle-piece",
        "icon_class": "icon-drupal", # O un ícono genérico de CMS
        "timeout": 900,
        "default_enabled": False,
        "description": "Identifica múltiples CMS (Drupal, Silverstripe, Joomla, WordPress) y enumera componentes.",
        "cli_params_config": [
            {"name": "threads", "label": "Hilos (-t)", "type": "number", "default": "32", "placeholder": "32"}
        ],
        "dangerous": False,
        "needs_shell": True, # Por la redirección '>'
    },
    "cmsmap": {
        "name": "CMSmap",
        "command_template": "cmsmap {target_url} -o {output_file}",
        "target_type": "url",
        "phase": "identification_web",
        "category": "CMS Specific Analysis",
        "category_display_name": "Análisis Específico de CMS",
        "category_icon_class": "icon-puzzle-piece",
        "icon_class": "icon-cogs", # Icono genérico
        "timeout": 1200,
        "default_enabled": False,
        "description": "Identifica CMS y ejecuta comprobaciones básicas de vulnerabilidades.",
        "cli_params_config": [],
        "dangerous": False,
        "needs_shell": False,
    },

    "sqlmap_batch": {
        "name": "SQLMap (Detection)",
        "command_template": "sqlmap -u \"{target_url_with_params}\" --batch --level=3 --risk=1 --technique=BEUSTQ --forms --crawl=2 -o --output-dir={output_file_dir}", # SQLMap guarda en directorio
        "target_type": "url_with_params", # e.g., http://example.com/vuln.php?id=1
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "icon-bomb",
        "icon_class": "icon-database",
        "timeout": 3600, # Puede ser largo
        "default_enabled": False,
        "description": "Detección de inyección SQL (sin explotación).",
        "cli_params_config": [
            {"name": "level", "label": "Nivel (--level)", "type": "select", "default": "3", "options": ["1","2","3","4","5"]},
            {"name": "risk", "label": "Riesgo (--risk)", "type": "select", "default": "1", "options": ["1","2","3"]},
            {"name": "crawl_depth", "label": "Profundidad Crawl (--crawl)", "type": "number", "default": "2", "placeholder": "2"}
        ],
        "dangerous": True, # Incluso en detección, puede ser intrusivo
        "needs_shell": False, # SQLMap es un script Python, pero el comando puede tener comillas
    },
    "nuclei_specific_vulns": {
        "name": "Nuclei (Specific Vulns)",
        "command_template": "nuclei -u {target_url} -t {nuclei_templates} -o {output_file_json} -json",
        "target_type": "url",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "icon-bomb",
        "icon_class": "icon-bullseye",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de clases específicas de vulnerabilidades (SSRF, SSTI, LFI, etc.) con plantillas Nuclei.",
        "cli_params_config": [
            {"name": "nuclei_templates", "label": "Plantillas (-t)", "type": "text", "default": "http/misconfiguration/,http/vulnerabilities/", "placeholder": "ruta/a/plantillas/,http/cves/"}
        ],
        "dangerous": False, # Depende de las plantillas
        "needs_shell": False,
    },
    "commix": {
        "name": "Commix (Command Inj. Detection)",
        "command_template": "commix -u \"{target_url_with_params}\" --batch --level=3 -o {output_file}", # Commix puede necesitar --output-dir
        "target_type": "url_with_params",
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "icon-bomb",
        "icon_class": "icon-terminal",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de inyección de comandos.",
        "cli_params_config": [
            {"name": "level", "label": "Nivel (--level)", "type": "select", "default": "3", "options": ["1","2","3","4","5"]}
        ],
        "dangerous": True, # Puede ser muy intrusivo
        "needs_shell": False,
    },
    "xsser": {
        "name": "XSSer (XSS Detection)",
        "command_template": "xsser -u \"{target_url}\" --params \"{url_params_for_xsser}\" -Cw --heuristic --user-agent \"Mozilla/5.0\" -o {output_file_xml}", # XSSer puede necesitar -o para archivo
        "target_type": "url_and_params", # Tipo especial, necesita URL base y parámetros separados
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "icon-bomb",
        "icon_class": "icon-code",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de Cross-Site Scripting (XSS).",
        "cli_params_config": [
        ],
        "dangerous": True, # Intenta inyectar XSS
        "needs_shell": False,
    },
    "lfisuite_scan": {
        "name": "LFISuite (LFI/RFI Scan)",
        "command_template": "lfisuite -u \"{target_url_with_lfi_fuzz_param}\" --scan -w {lfi_wordlist} -o {output_file_dir}", # LFISuite puede guardar en directorio
        "target_type": "url_with_lfi_fuzz_param", # e.g., http://example.com/page.php?file=FUZZ
        "phase": "identification_web",
        "category": "Specific Vulnerability Detection",
        "category_display_name": "Detección Específica de Vulnerabilidades",
        "category_icon_class": "icon-bomb",
        "icon_class": "icon-file-import",
        "timeout": 1800,
        "default_enabled": False,
        "description": "Detección de vulnerabilidades de Inclusión Local y Remota de Archivos (LFI/RFI).",
        "cli_params_config": [
            {"name": "lfi_wordlist", "label": "Wordlist LFI (-w)", "type": "text", "default": "/usr/share/seclists/Fuzzing/LFI/LFI-Jhaddix.txt", "placeholder": "ruta/a/lfi_wordlist.txt"}
        ],
        "dangerous": True, # Intenta incluir archivos
        "needs_shell": False,
    },
}


PROFILES_CONFIG = {
    "Full Recon (Domain)": {
        "description": "Reconocimiento exhaustivo de un dominio (subdominios, DNS, OSINT).",
        "icon_class": "icon-search-plus",
        "tools": ["amass_enum", "subfinder", "findomain", "theharvester", "dnsrecon", "nmap_dns_scripts"],
        "params_override": {
            "amass_enum": {"min-for-recursive": "2"}, # Ejemplo de override
        }
    },
    "Quick Web Scan (URL)": {
        "description": "Escaneo web rápido de un URL (tecnologías, directorios comunes, vulnerabilidades básicas).",
        "icon_class": "icon-zap",
        "tools": ["httpx_tech", "whatweb", "ffuf_common", "nuclei_tech_info", "nuclei_vulns"],
         "params_override": {
            "ffuf_common": {"wordlist_path": "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt"}
        }
    },
    "Infrastructure Scan (IP/Host)": {
        "description": "Escaneo de infraestructura en un IP o Host (puertos comunes, servicios).",
        "icon_class": "icon-network-wired",
        "tools": ["nmap_top_ports", "naabu"],
        "params_override": {}
    },
    "CMS Scan (WordPress URL)": {
        "description": "Escaneo específico para un sitio WordPress.",
        "icon_class": "icon-wordpress",
        "tools": ["wpscan", "whatweb", "nuclei_vulns"],
        "params_override": {
            "nuclei_vulns": {"tags": "wordpress,cve,misconfiguration"}
        }
    }
}


def get_tools_definition():
    """Devuelve la configuración de herramientas."""
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
        "raw_commands": TOOLS_CONFIG, # Para compatibilidad con el engine.py original
        "presets": PROFILES_CONFIG    # Para compatibilidad con el engine.py original
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
                              Se espera que este diccionario sea la fuente de verdad completa
                              o una actualización que se fusionará correctamente.
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

    
    if 'logs' in summary_data_to_save:
        current_summary_on_disk['logs'] = summary_data_to_save['logs']
    elif 'logs' not in current_summary_on_disk: # Asegurar que 'logs' exista
         current_summary_on_disk['logs'] = []


    if 'tool_progress' in summary_data_to_save:
        current_summary_on_disk['tool_progress'] = summary_data_to_save['tool_progress']
    elif 'tool_progress' not in current_summary_on_disk: # Asegurar que 'tool_progress' exista
        current_summary_on_disk['tool_progress'] = {}

    for key, value in summary_data_to_save.items():
        if key not in ['logs', 'tool_progress']: # Ya manejados
            current_summary_on_disk[key] = value
            
    current_summary_on_disk.setdefault('job_id', Path(job_path).name)
    current_summary_on_disk.setdefault('status', 'UNKNOWN')
    current_summary_on_disk.setdefault('overall_progress', 0)


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
    job_id_from_path = Path(job_path).name # Para usar en caso de error

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
            summary_data.setdefault('start_time', None)
            summary_data.setdefault('creation_timestamp', None) # Añadido por si se usa
            summary_data.setdefault('end_timestamp', None)
            summary_data.setdefault('zip_path', None)
            summary_data.setdefault('error_message', None)
            return summary_data
        except (IOError, json.JSONDecodeError) as e:
            print(f"WARN: No se pudo leer o decodificar summary.json en {job_path} (Job ID: {job_id_from_path}): {e}")
    
    return {
        'job_id': job_id_from_path,
        'status': 'NOT_FOUND', # O 'ERROR_LOADING_SUMMARY'
        'error_message': 'summary.json no encontrado o corrupto.',
        'overall_progress': 0,
        'logs': [{'timestamp': get_current_timestamp(), 'level': 'error', 'message': 'summary.json no encontrado o corrupto.', 'is_html': False}],
        'tool_progress': {},
        'targets': [],
        'start_time': None,
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
            if job_dir.is_dir() and (job_dir / 'summary.json').exists(): # Solo procesar si summary.json existe
                job_summary = get_scan_status_from_file(str(job_dir))
                jobs.append({
                    'id': job_summary.get('job_id', job_dir.name), # 'id' para consistencia con frontend
                    'status': job_summary.get('status', 'UNKNOWN'),
                    'timestamp': job_summary.get('start_timestamp') or job_summary.get('creation_timestamp'),
                    'targets': job_summary.get('targets', []),
                    'zip_path': job_summary.get('zip_path')
                })
    return sorted(jobs, key=lambda j: j.get('timestamp') or '0', reverse=True)

