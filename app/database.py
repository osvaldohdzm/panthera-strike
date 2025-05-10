import os
import click
from flask import current_app
from flask.cli import with_appcontext
from .extensions import db  # Importar la instancia de SQLAlchemy

def init_db():
    schema_path = os.path.join(current_app.root_path, '..', 'schema.sql')
    if not os.path.exists(schema_path):
        current_app.logger.error(f"No se encontró el archivo schema.sql en {schema_path}")
        return
    
    with current_app.open_resource(schema_path) as f:
        sql_script = f.read().decode('utf8')
    
    connection = db.engine.connect()
    transaction = connection.begin()
    try:
        raw_connection = connection.connection # Accede a la conexión DBAPI subyacente
        raw_connection.executescript(sql_script)
        transaction.commit()
        current_app.logger.info("Base de datos inicializada desde schema.sql.")
    except Exception as e:
        transaction.rollback()
        current_app.logger.error(f"Error al inicializar la base de datos desde schema.sql: {e}")
    finally:
        connection.close()

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    app.cli.add_command(init_db_command) # Añade el comando init-db a Flask CLI