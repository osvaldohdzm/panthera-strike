#!/bin/bash

# --- Configuration ---
OUTPUT_FILE="code_context.txt"
REGEX_FILTER_LINES='^\s*#(?!.*\.py).*'

declare -A GROUP_FILES
GROUP_FILES[frontend]="static onlye"
GROUP_FILES[backend]="app scanner static templates utils"

EXCLUDE_EXTENSIONS=(jpg png pyc log zip tar gz)
EXCLUDE_DIRS=(.git node_modules __pycache__)
EXCLUDE_FILES=(README.md LICENSE)

# Validate input
if [ $# -ne 1 ]; then
    echo "Usage: $0 <group>"
    echo "Available GROUP_FILES:"
    for group in "${!GROUP_FILES[@]}"; do
        echo "  - $group"
    done
    exit 1
fi

GROUP="$1"

if [[ -z "${GROUP_FILES[$GROUP]}" ]]; then
    echo "Invalid group: $GROUP"
    echo "Available GROUP_FILES:"
    for group in "${!GROUP_FILES[@]}"; do
        echo "  - $group"
    done
    exit 1
fi

echo -n > "$OUTPUT_FILE"

# Recorrer carpetas del grupo
for folder in ${GROUP_FILES[$GROUP]}; do
    if [ -d "$folder" ]; then
        find "$folder" \( \
            $(for dir in "${EXCLUDE_DIRS[@]}"; do echo -n "-name $dir -o "; done | sed 's/ -o $//') \
        \) -prune -o -type f ! \( \
            $(for ext in "${EXCLUDE_EXTENSIONS[@]}"; do echo -n "-iname '*.$ext' -o "; done | sed 's/ -o $//') \
        \) ! \( \
            $(for file in "${EXCLUDE_FILES[@]}"; do echo -n "-name '$file' -o "; done | sed 's/ -o $//') \
        \) -print0 | while IFS= read -r -d $'\0' file; do
            echo "===== $file =====" >> "$OUTPUT_FILE"
            grep --binary-files=without-match -vP "$REGEX_FILTER_LINES" "$file" >> "$OUTPUT_FILE"
            echo -e "\n\n" >> "$OUTPUT_FILE"
        done
    fi
done

echo "Context successfully written to $OUTPUT_FILE"
