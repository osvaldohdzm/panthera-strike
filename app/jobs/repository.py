import sqlite3
import json
import os
from pathlib import Path
from utils import helpers # Asumiendo que helpers.py está en utils/

class JobRepository:
    def __init__(self, db_path, jobs_base_dir, logger):
        self.db_path = db_path
        self.jobs_base_dir = Path(jobs_base_dir)
        self.logger = logger

    def _get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_job_record(self, job_id, name, status, targets_input, creation_timestamp, job_config_path, overall_progress=0):
        """Crea un registro de trabajo en la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO job (id, name, status, targets_input, creation_timestamp, job_config_path, overall_progress) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, name, status, json.dumps(targets_input), creation_timestamp, job_config_path, overall_progress)
            )
            conn.commit()
            self.logger.info(f"Job record {job_id} created in database.")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating job record {job_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def update_job_status(self, job_id, status, start_timestamp=None, end_timestamp=None):
        """Actualiza el estado de un trabajo en la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            if start_timestamp and status == "RUNNING":
                cursor.execute("UPDATE job SET status = ?, start_timestamp = ? WHERE id = ?", (status, start_timestamp, job_id))
            elif end_timestamp:
                cursor.execute("UPDATE job SET status = ?, end_timestamp = ? WHERE id = ?", (status, end_timestamp, job_id))
            else:
                cursor.execute("UPDATE job SET status = ? WHERE id = ?", (status, job_id))
            conn.commit()
            self.logger.info(f"Job {job_id} status updated to {status} in database.")
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Database error updating job status for {job_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def update_job_progress(self, job_id, progress):
        """Actualiza el progreso general de un trabajo en la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE job SET overall_progress = ? WHERE id = ?", (progress, job_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Database error updating job progress for {job_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_job_by_id(self, job_id):
        """Obtiene un trabajo por su ID desde la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job WHERE id = ?", (job_id,))
            job_data = cursor.fetchone()
            return dict(job_data) if job_data else None
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching job {job_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_all_jobs(self):
        """Obtiene todos los trabajos de la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, status, creation_timestamp, start_timestamp, end_timestamp, overall_progress FROM job ORDER BY creation_timestamp DESC")
            jobs = [dict(row) for row in cursor.fetchall()]
            return jobs
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching all jobs: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def delete_job_record(self, job_id):
        """Elimina un registro de trabajo de la base de datos."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job WHERE id = ?", (job_id,))
            conn.commit()
            self.logger.info(f"Job record {job_id} deleted from database.")
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Database error deleting job record {job_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_job_summary_data(self, job_id):
        """Carga los datos del archivo summary.json para un trabajo específico."""
        job_path = self.jobs_base_dir / job_id
        return helpers.get_scan_status_from_file(str(job_path)) # Reutiliza la función de helpers

    def save_job_summary_data(self, job_id, data):
        """Guarda los datos en el archivo summary.json para un trabajo específico."""
        job_path = self.jobs_base_dir / job_id
        helpers.save_job_summary(str(job_path), data) # Reutiliza la función de helpers
        self.logger.debug(f"Job summary data for {job_id} saved.")

    def get_job_output_file_path(self, job_id, filename):
        """Construye y valida la ruta a un archivo de salida de herramienta."""
        if '..' in filename or filename.startswith('/'):
            self.logger.warning(f"Attempted path traversal for job {job_id}, filename {filename}")
            return None
        
        job_path = self.jobs_base_dir / job_id
        file_path = job_path / "tool_outputs" / filename
        
        if file_path.exists() and file_path.is_file():
            try:
                common_path = os.path.commonpath([os.path.realpath(file_path), os.path.realpath(job_path / "tool_outputs")])
                if common_path == os.path.realpath(job_path / "tool_outputs"):
                    return str(file_path)
                else:
                    self.logger.warning(f"Requested file {filename} for job {job_id} is outside the allowed directory.")
                    return None
            except ValueError: # Si las rutas están en diferentes unidades en Windows, por ejemplo.
                self.logger.warning(f"Could not determine common path for {filename} in job {job_id}.")
                return None
        
        self.logger.warning(f"File {filename} not found or not accessible for job {job_id} at {file_path}")
        return None

    def get_job_directory(self, job_id):
        """Devuelve la ruta al directorio del trabajo."""
        return self.jobs_base_dir / job_id