import sqlite3
import os
import click
from flask import current_app, g
from flask.cli import with_appcontext

# Obtener la ruta de la base de datos desde la configuración de la aplicación
def get_db_path():
    # Asegurarse de que esto se llama dentro de un contexto de aplicación
    return current_app.config['DATABASE_PATH']

def get_db():
    if 'db' not in g:
        db_path = get_db_path()
        # Asegurarse de que el directorio de la instancia exista
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    # La ruta al schema.sql podría necesitar ajuste o ser configurable
    schema_path = os.path.join(current_app.root_path, '..', 'schema.sql')
    if not os.path.exists(schema_path):
        current_app.logger.error(f"No se encontró el archivo schema.sql en {schema_path}")
        return
    with current_app.open_resource(schema_path) as f:
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

# Función para registrar los comandos de la base de datos con la aplicación Flask
def init_app(app):
    app.teardown_appcontext(close_db) # Llama a close_db cuando el contexto de la aplicación termina
    app.cli.add_command(init_db_command) # Añade el comando init-db a Flask CLI