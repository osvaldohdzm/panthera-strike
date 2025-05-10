from flask import request, jsonify, current_app, send_from_directory, abort
from flask_login import login_required, current_user # Asumiendo que current_user se usa para permisos
import os
import json
from pathlib import Path # Para manejo de rutas

from . import jobs_bp
from .services import JobService
from utils import helpers # Para cargar configuraciones si es necesario

_panthera_tools_config = None

def get_job_service():
    """
    Obtiene una instancia de JobService con la configuración actual de la app.
    Carga la configuración de herramientas si aún no se ha hecho.
    """
    global _panthera_tools_config
    if _panthera_tools_config is None:
        if 'PANTHERA_TOOLS_CONFIG' in current_app.config:
            _panthera_tools_config = current_app.config['PANTHERA_TOOLS_CONFIG']
        else:
            try:
                _panthera_tools_config = helpers.get_tools_definition()
                current_app.config['PANTHERA_TOOLS_CONFIG'] = _panthera_tools_config # Cachear en app.config
            except Exception as e:
                current_app.logger.error(f"Error crítico: No se pudo cargar la configuración de herramientas: {e}")
                _panthera_tools_config = {} # Fallback a un diccionario vacío para evitar errores posteriores

    return JobService(
        db_path=current_app.config['DATABASE_PATH'],
        jobs_base_dir=current_app.config['JOBS_BASE_DIR'],
        logger=current_app.logger,
        tools_config=_panthera_tools_config,
        app_instance_path=current_app.instance_path # o current_app.root_path
    )

@jobs_bp.route('/scan/start', methods=['POST'])
@login_required
def start_scan_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "El cuerpo de la solicitud debe ser JSON."}), 400

    targets_input = data.get("targets")
    selected_tools_payload = data.get("tools") # Espera [{id, cli_params, additional_args}, ...]
    advanced_options_input = data.get("advanced_options", {})
    scan_name_input = data.get("scan_name") # Opcional, el servicio puede generar uno

    if not targets_input or not isinstance(targets_input, list) or not all(isinstance(t, str) for t in targets_input):
        return jsonify({"error": "Faltan objetivos o el formato es incorrecto (se espera una lista de strings)."}), 400
    
    targets = [t.strip() for t in targets_input if t.strip()]
    if not targets:
        return jsonify({"error": "No se proporcionaron objetivos válidos."}), 400

    if not selected_tools_payload or not isinstance(selected_tools_payload, list):
        return jsonify({"error": "Faltan herramientas seleccionadas o el formato es incorrecto."}), 400

    job_service = get_job_service()
    try:
        job_id, _ = job_service.create_job( # job_path_str no se usa directamente en la respuesta aquí
            targets=targets,
            selected_tools_payload=selected_tools_payload,
            advanced_options=advanced_options_input,
            scan_name=scan_name_input
        )
        
        success_starting = job_service.start_job_processing(job_id)
        if success_starting:
            return jsonify({"message": "Trabajo de escaneo iniciado.", "job_id": job_id}), 202
        else:
            current_app.logger.error(f"Trabajo {job_id} creado pero no pudo iniciarse inmediatamente por JobService.")
            return jsonify({"error": f"Trabajo {job_id} creado pero no pudo iniciarse. Verifique el estado del job."}), 500

    except ValueError as ve:
        current_app.logger.warning(f"Error de validación al crear/iniciar job: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"Error crítico al iniciar escaneo: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al iniciar el escaneo."}), 500


@jobs_bp.route('/scan/status/<job_id>', methods=['GET'])
@login_required
def scan_status_route(job_id):
    job_service = get_job_service()
    try:
        summary = job_service.get_job_summary_data(job_id) # Este método ya combina DB y archivo
        if summary:
            response_data = {
                "job_id": summary.get("job_id", job_id),
                "status": summary.get("status", "UNKNOWN"),
                "overall_progress": summary.get("overall_progress", 0),
                "start_time": summary.get("start_timestamp"), # El summary.json usa start_timestamp
                "end_time": summary.get("end_timestamp"),
                "targets": summary.get("targets", []),
                "logs": summary.get("logs", []),
                "tool_progress": summary.get("tool_progress", {}),
                "error_message": summary.get("error_message"),
                "zip_path": summary.get("zip_path"), # zip_path del summary (actualizado por el engine)
            }
            return jsonify(response_data), 200
        else:
            return jsonify({"error": "Job no encontrado o no autorizado."}), 404
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estado para job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al obtener estado del job."}), 500


@jobs_bp.route('/jobs', methods=['GET'])
@login_required
def list_jobs_route():
    job_service = get_job_service()
    try:
        jobs_list = job_service.get_all_jobs_summary() 
        formatted_jobs = []
        for job_data in jobs_list:
            formatted_jobs.append({
                "id": job_data.get("id"),
                "status": job_data.get("status"),
                "timestamp": job_data.get("start_timestamp") or job_data.get("creation_timestamp"),
                "targets": job_data.get("targets", []), 
                "zip_path": job_data.get("zip_path"),
            })
        return jsonify(formatted_jobs), 200
    except Exception as e:
        current_app.logger.error(f"Error listando jobs: {e}", exc_info=True)
        return jsonify({"error": "Error al recuperar la lista de trabajos."}), 500


@jobs_bp.route('/scan/cancel/<job_id>', methods=['POST'])
@login_required
def cancel_scan_route(job_id):
    job_service = get_job_service()
    try:
        success = job_service.request_cancel_job(job_id)
        if success:
            return jsonify({"message": f"Solicitud de cancelación para el job {job_id} enviada."}), 200
        else:
            return jsonify({"error": f"No se pudo solicitar la cancelación para el job {job_id}. Verifique su estado."}), 400
    except Exception as e:
        current_app.logger.error(f"Error cancelando job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al cancelar el trabajo."}), 500


@jobs_bp.route('/results/download/<job_id>/archive', methods=['GET'])
@login_required
def download_job_archive_route(job_id):
    job_service = get_job_service()
    try:

        job_data = job_service.get_job_summary_data(job_id) # Podría ser get_job_db_record si solo necesitas zip_path
        if not job_data:
            return jsonify({"error": "Job no encontrado."}), 404
        
        zip_filename_from_summary = job_data.get("zip_path")
        if not zip_filename_from_summary:
            return jsonify({"error": "Archivo ZIP no disponible para este job."}), 404
        
        actual_zip_filename = Path(zip_filename_from_summary).name 

        zip_file_path = job_service.jobs_base_dir / actual_zip_filename
        
        if not zip_file_path.is_file():
            current_app.logger.error(f"Archivo ZIP {zip_file_path} no encontrado en disco para job {job_id}.")
            return jsonify({"error": "Archivo ZIP no encontrado en el servidor."}), 404

        return send_from_directory(
            directory=str(zip_file_path.parent),
            path=zip_file_path.name, # En Flask >= 2.0, 'path' es el nombre correcto
            as_attachment=True,
            download_name=actual_zip_filename # Nombre que verá el usuario
        )
    except Exception as e:
        current_app.logger.error(f"Error al enviar archivo ZIP para job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "No se pudo enviar el archivo ZIP."}), 500


@jobs_bp.route('/scan/delete/<job_id>', methods=['DELETE'])
@login_required
def delete_scan_job_route(job_id):
    job_service = get_job_service()
    try:
        success = job_service.delete_job_data(job_id)
        if success:
            return jsonify({"message": f"Job {job_id} y sus datos eliminados correctamente."}), 200
        else:
            return jsonify({"error": f"No se pudo eliminar el job {job_id}. Puede que no exista."}), 404
    except Exception as e:
        current_app.logger.error(f"Error eliminando job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al eliminar el job."}), 500



@jobs_bp.route('/scan/archive/<job_id>', methods=['POST'])
@login_required
def archive_scan_job_route(job_id):
    job_service = get_job_service()
    try:
        success = job_service.archive_job(job_id) # Necesitarías implementar este método en JobService
        if success:
            return jsonify({"message": f"Job {job_id} archivado correctamente."}), 200
        else:
            return jsonify({"error": f"No se pudo archivar el job {job_id}. Puede que no exista o ya esté archivado."}), 400
    except Exception as e:
        current_app.logger.error(f"Error archivando job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al archivar el job."}), 500

@jobs_bp.route('/scan/unarchive/<job_id>', methods=['POST'])
@login_required
def unarchive_scan_job_route(job_id):
    job_service = get_job_service()
    try:
        success = job_service.unarchive_job(job_id) # Necesitarías implementar este método
        if success:
            return jsonify({"message": f"Job {job_id} desarchivado correctamente."}), 200
        else:
            return jsonify({"error": f"No se pudo desarchivar el job {job_id}."}), 400
    except Exception as e:
        current_app.logger.error(f"Error desarchivando job {job_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al desarchivar el job."}), 500