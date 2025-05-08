#!/bin/bash

# Nombre del entorno virtual
VENV_DIR="venv"

# Comprobar si Python 3 está instalado
if ! command -v python3 &> /dev/null
then
    echo "Python 3 no está instalado. Por favor, instálalo para continuar."
    exit 1
fi

# Crear entorno virtual si no existe
if [ ! -d "$VENV_DIR" ]; then
    echo "Creando entorno virtual en '$VENV_DIR'..."
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo "Error al crear el entorno virtual."
        exit 1
    fi
else
    echo "Entorno virtual '$VENV_DIR' ya existe."
fi

# Activar entorno virtual
echo "Activando entorno virtual..."
source $VENV_DIR/bin/activate
if [ $? -ne 0 ]; then
    echo "Error al activar el entorno virtual."
    exit 1
fi

# Instalar dependencias
if [ -f "requirements.txt" ]; then
    echo "Instalando dependencias desde requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error al instalar las dependencias."
        exit 1
    fi
else
    echo "Archivo requirements.txt no encontrado. Omitiendo instalación de dependencias."
fi

# Iniciar la aplicación (el usuario debe cambiar app.py si su archivo principal tiene otro nombre)
APP_FILE="app.py" 

if [ -f "$APP_FILE" ]; then
    echo "Iniciando la aplicación $APP_FILE..."
    python3 $APP_FILE
else
    echo "Archivo de aplicación '$APP_FILE' no encontrado."
    echo "Por favor, asegúrate de que el archivo principal de tu aplicación Python exista y esté nombrado correctamente como '$APP_FILE' en este script (start.sh), o crea un archivo llamado '$APP_FILE'."
fi


echo "Script finalizado."