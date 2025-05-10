from flask_login import UserMixin
# from app.extensions import db # Descomentar si se usa SQLAlchemy y se define User como un modelo de DB

class User(UserMixin):
    # Si se usa SQLAlchemy, esta clase heredaría de db.Model
    # y tendría columnas definidas como db.Column(...)
    # Ejemplo básico sin ORM, asumiendo que los datos se cargan desde la DB en routes.py
    def __init__(self, id, username):
        self.id = id
        self.username = username

    # Si se usa SQLAlchemy, se necesitarían métodos para guardar, eliminar, etc.
    # y el __init__ podría ser diferente o manejado por el ORM.

    # Ejemplo de cómo podría ser con SQLAlchemy (simplificado):
    # id = db.Column(db.Integer, primary_key=True)
    # username = db.Column(db.String(80), unique=True, nullable=False)
    # password_hash = db.Column(db.String(120), nullable=False)

    # def set_password(self, password):
    #     self.password_hash = generate_password_hash(password)

    # def check_password(self, password):
    #     return check_password_hash(self.password_hash, password)