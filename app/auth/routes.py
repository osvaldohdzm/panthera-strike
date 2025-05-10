from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash # Importar generate_password_hash si se va a usar para crear usuarios
from . import auth_bp
from .models import User # Suponiendo que User se moverá a models.py
from app.extensions import login_manager
from app.database import get_db # Para interactuar con la base de datos directamente aquí si es necesario

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user_data = db.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
    if user_data:
        return User(id=user_data['id'], username=user_data['username'])
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index')) # Suponiendo que la ruta principal se llamará 'main.index'
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user_data = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user_obj = User(id=user_data['id'], username=user_data['username'])
            login_user(user_obj)
            flash('Inicio de sesión exitoso.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index')) # Cambiar a la ruta principal deseada
        else:
            flash('Credenciales inválidas. Por favor, inténtelo de nuevo.', 'danger')
            
    return render_template('login.html') # Asegurarse de que login.html existe en templates/

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada exitosamente.', 'info')
    return redirect(url_for('auth.login'))

