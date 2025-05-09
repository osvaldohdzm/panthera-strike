DROP TABLE IF EXISTS user;
CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);

DROP TABLE IF EXISTS job;
CREATE TABLE job (
  id TEXT PRIMARY KEY,                  -- Identificador único del trabajo (ej. scan_timestamp_microsegundos)
  user_id INTEGER,                    -- Opcional: para vincular trabajos a usuarios
  status TEXT NOT NULL,                 -- PENDING, INITIALIZING, RUNNING, COMPLETED, COMPLETED_WITH_ERRORS, REQUEST_CANCEL, CANCELLED, ERROR
  targets TEXT,                       -- JSON string de la lista de objetivos
  selected_tools_config TEXT,         -- JSON string de las herramientas y sus parámetros para este job
  advanced_options TEXT,              -- JSON string de opciones avanzadas globales
  creation_timestamp DATETIME NOT NULL,
  start_timestamp DATETIME,
  end_timestamp DATETIME,
  overall_progress INTEGER DEFAULT 0,
  results_path TEXT,                  -- Ruta al directorio de resultados del job
  zip_path TEXT,                      -- Ruta (relativa a la app o URL) al archivo ZIP de resultados
  error_message TEXT,                 -- Mensaje de error si el job falla
  FOREIGN KEY (user_id) REFERENCES user (id)
);