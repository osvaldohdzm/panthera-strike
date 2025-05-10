#!/bin/bash

# clean_code.sh
# Este script limpia los comentarios de los archivos Python y HTML
# de forma selectiva en el proyecto.

# Directorio raíz del proyecto (asumiendo que el script está en ./scripts)
PROJECT_ROOT="$(dirname "$0")/.."

echo "Iniciando limpieza de código..."

# 1. Limpiar comentarios en archivos Python (.py)
#    Borra líneas que son completamente comentarios (iniciando con #, posiblemente con espacios antes)
#    No afecta a los comentarios que están en la misma línea que el código.
echo "Limpiando archivos Python..."
find "$PROJECT_ROOT" -type f -name "*.py" -print0 | while IFS= read -r -d $'\0' file; do
    echo "Procesando archivo Python: $file"
    # Usamos sed con la opción -i para editar in-place (crea un backup si se le da una extensión, ej: -i.bak)
    # La expresión regular '^s*#.*$' elimina las líneas que comienzan con # (y posibles espacios antes)
    sed -i '/^\s*#.*$/d' "$file"
done

# 2. Limpiar comentarios en archivos HTML (.html)
#    Borra comentarios HTML echo "Limpiando archivos HTML..."
find "$PROJECT_ROOT" -type f -name "*.html" -print0 | while IFS= read -r -d $'\0' file; do
    echo "Procesando archivo HTML: $file"
    # Usamos sed para reemplazar los comentarios HTML con nada.
    # La 'g' al final es para reemplazar todas las ocurrencias en una línea.
    # Nota: Esto puede tener limitaciones con comentarios HTML multilínea muy complejos
    # o anidados, aunque para la mayoría de los casos debería funcionar.
    # Para casos más complejos, herramientas específicas de parsing HTML podrían ser más robustas.
    sed -i -e 's///g' "$file"
done

echo "Limpieza de código completada."