#!/bin/bash

# clean_code.sh
# Limpia comentarios en archivos Python, HTML y CSS.

# Directorio raíz del proyecto
PROJECT_ROOT="$(dirname "$0")/.."

echo "Iniciando limpieza de código..."

# Detectar sed compatible
if sed --version >/dev/null 2>&1; then
    # GNU sed
    SED_INPLACE=(-i)
else
    # BSD/macOS sed
    SED_INPLACE=(-i '')
fi

# 1. Limpiar archivos Python (.py)
echo "Limpiando archivos Python..."
find "$PROJECT_ROOT" -type f -name "*.py" -print0 | while IFS= read -r -d '' file; do
    echo "Procesando archivo Python: $file"
    sed "${SED_INPLACE[@]}" '/^\s*#.*$/d' "$file"
done

# 2. Limpiar archivos HTML (.html)
echo "Limpiando archivos HTML..."
find "$PROJECT_ROOT" -type f -name "*.html" -print0 | while IFS= read -r -d '' file; do
    echo "Procesando archivo HTML: $file"
    sed "${SED_INPLACE[@]}" -E ':a;N;$!ba;s/<!--(.|\n)*?-->//g' "$file"
done

# 3. Limpiar archivos CSS (.css)
echo "Limpiando archivos CSS..."
find "$PROJECT_ROOT" -type f -name "*.css" -print0 | while IFS= read -r -d '' file; do
    echo "Procesando archivo CSS: $file"
    sed "${SED_INPLACE[@]}" -E ':a;N;$!ba;s/\/\*([^*]|\*[^/])*\*\///g' "$file"
done

# 4. Limpiar archivos JavaScript (.js)
echo "Limpiando archivos JavaScript..."
find "$PROJECT_ROOT" -type f -name "*.js" -print0 | while IFS= read -r -d '' file; do
    echo "Procesando archivo JavaScript: $file"
    # 4.1 Eliminar comentarios multilínea
    sed "${SED_INPLACE[@]}" -E ':a;N;$!ba;s/\/\*([^*]|\*[^/])*\*\///g' "$file"
    # 4.2 Eliminar líneas que son solo comentarios con //
    sed "${SED_INPLACE[@]}" -E '/^\s*\/\/.*$/d' "$file"
done

echo "Limpieza de código completada."
