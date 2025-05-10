import shlex
import re
from pathlib import Path

class CommandBuilder:
    def __init__(self, logger, tool_definition, job_id, target_value, tool_outputs_dir_str, user_cli_params=None):
        self.logger = logger
        self.tool_definition = tool_definition
        self.job_id = job_id
        self.target_value = target_value
        self.tool_outputs_dir = Path(tool_outputs_dir_str)
        self.user_cli_params = user_cli_params or {}
        self.tool_id = self.tool_definition.get('id', 'unknown_tool')

    def _generate_output_filename_base(self):
        from utils import helpers # Importación local para evitar dependencia circular a nivel de módulo
        return f"{self.tool_id}_{self.target_value.replace('://', '_').replace('/', '_').replace(':', '_')}_{helpers.get_current_timestamp_str()}"

    def build_command(self):
        command_template = self.tool_definition.get("command_template", "")
        if not command_template:
            self.logger.warning(f"Job {self.job_id}: No command template for tool {self.tool_id}")
            return None, None, None # command_list, command_str_for_log, actual_output_file_path

        tool_output_filename_base = self._generate_output_filename_base()
        final_command = command_template

        placeholders = {
            "{target}": self.target_value,
            "{target_domain}": self.target_value, # Asumir que target_value es el dominio si es el placeholder
            "{target_url}": self.target_value, # Asumir que target_value es la URL
            "{target_host_or_ip}": self.target_value,
            "{target_ip_range}": self.target_value,
            "{target_domain_or_ip}": self.target_value,
            "{target_wordpress_url}": self.target_value,
            "{target_joomla_url}": self.target_value,
            "{target_url_with_params}": self.target_value, 
            "{target_url_with_lfi_fuzz_param}": self.target_value
        }
        for ph, val in placeholders.items():
            final_command = final_command.replace(ph, shlex.quote(val))

        actual_output_file_path = self.tool_outputs_dir / f"{tool_output_filename_base}.txt" # Default
        if "{output_file_json}" in command_template:
            actual_output_file_path = self.tool_outputs_dir / f"{tool_output_filename_base}.json"
        elif "{output_file_xml}" in command_template:
            actual_output_file_path = self.tool_outputs_dir / f"{tool_output_filename_base}.xml"
        elif "{output_file_dir}" in command_template:
            actual_output_file_path = self.tool_outputs_dir 

        output_placeholders = {
            "{output_file}": str(self.tool_outputs_dir / f"{tool_output_filename_base}.txt"),
            "{output_file_base}": str(self.tool_outputs_dir / tool_output_filename_base),
            "{output_file_json}": str(self.tool_outputs_dir / f"{tool_output_filename_base}.json"),
            "{output_file_xml}": str(self.tool_outputs_dir / f"{tool_output_filename_base}.xml"),
            "{output_file_dir}": str(self.tool_outputs_dir) 
        }
        for ph, val_path_str in output_placeholders.items():
            final_command = final_command.replace(ph, shlex.quote(val_path_str))

        try:
            base_cmd_tool = shlex.split(final_command)[0]
            remaining_template_parts = shlex.split(final_command)[1:]
            remaining_template = " ".join(remaining_template_parts)
        except IndexError: # Si final_command está vacío o solo tiene espacios
            base_cmd_tool = final_command.strip() # Tomar lo que haya
            remaining_template = ""
        except ValueError as e_shlex_split_base: # Error en shlex.split (e.g. comillas no cerradas)
            self.logger.error(f"Job {self.job_id}: Error inicial al parsear plantilla de comando para {self.tool_id}: {e_shlex_split_base}. Plantilla: {final_command}")
            return None, None, None
        
        for p_key, p_val in self.user_cli_params.items():
            if p_val is not None and str(p_val).strip() != "":
                remaining_template = remaining_template.replace(f"{{{p_key}}}", shlex.quote(str(p_val)))

        if self.tool_definition.get("cli_params_config"):
            for p_conf in self.tool_definition["cli_params_config"]:
                placeholder = f"{{{p_conf['name']}}}"
                if placeholder in remaining_template:
                    default_val = p_conf.get("default")
                    if default_val is not None and str(default_val).strip() != "":
                        remaining_template = remaining_template.replace(placeholder, shlex.quote(str(default_val)))
        
        remaining_template = re.sub(r"\{[a-zA-Z0-9_]+\}", "", remaining_template)
        remaining_template = ' '.join(remaining_template.split()) 
        
        final_command_list = []
        final_command_str_for_log = ""
        try:
            if not self.tool_definition.get("needs_shell", False):
                final_command_list = [base_cmd_tool] + shlex.split(remaining_template)
                final_command_str_for_log = " ".join(final_command_list)
            else:
                final_command_str_for_log = base_cmd_tool + " " + remaining_template
                final_command_list = final_command_str_for_log 
        except ValueError as e_shlex: # Error en shlex.split (e.g. comillas no cerradas)
            self.logger.error(f"Job {self.job_id}: Error al parsear argumentos finales para {self.tool_id}: {e_shlex}. Comando parcial: {base_cmd_tool + ' ' + remaining_template}")
            return None, None, None

        return final_command_list, final_command_str_for_log, actual_output_file_path