#!/bin/bash

# --- Configuration ---
OUTPUT_FILE="code_context.txt"

REGEX_FILTER_LINES='^\s*#(?!.*\.py).*'

EXCLUDE_EXTENSIONS=(
  "gitignore" "jpg" "jpeg" "png" "gif" "webp" "bmp"
  "mp4" "mkv" "avi" "mov" "flv" "webm"
  "mp3" "wav" "ogg" "flac" "aac"
  "ico" "svg" "pdf" "ttf" "woff" "woff2" "eot"
  "zip" "tar" "gz" "rar" "7z" "bz2" "xz"
  "pyc" "pyd" "pyo" "whl" "egg"
  "lock" "sum"
  "bin" "exe" "dll" "so" "o" "a" "lib" "class" "jar" "war" "ear"
  "DS_Store"
  "log"
  "bak" "swp" "swo"
)

EXCLUDE_DIRS=(
  ".git" "node_modules" "__pycache__" ".venv" "env" "venv" "ENV" ".env"
  "build" "dist" "results" "scan_results" "target" "out" "bin" "obj"
  ".idea" ".vscode" ".settings" ".project" ".classpath"
  ".tox" ".nox" ".pytest_cache" ".eggs" ".mypy_cache"
  ".scrapy" ".hypothesis" "instance" ".webassets-cache"
  "docs" "doc" "site" "_site" "javadoc"
  "testdata" "fixtures" "examples" "samples"
  "migrations"
  "vendor" "third_party" "external"
  "coverage"
  "logs"
  "temp" "tmp"
)

EXCLUDE_FILES=(
  "tools_config.json" "panthera.db"
  "MANIFEST.in" "setup.cfg" "setup.py"
  ".DS_Store" "Thumbs.db"
  "Jenkinsfile" "Dockerfile" "docker-compose.yml"
  "Makefile" "pom.xml" "build.gradle"
  "README" "LICENSE" "CONTRIBUTING"
)

output_file_basename=$(basename "$OUTPUT_FILE")
[[ ! " ${EXCLUDE_FILES[*]} " =~ " ${output_file_basename} " ]] && EXCLUDE_FILES+=("$output_file_basename")

echo -n > "$OUTPUT_FILE"

for input_path in "$@"; do
    if [ -f "$input_path" ]; then
        filename=$(basename "$input_path")
        extension="${filename##*.}"

        if [[ " ${EXCLUDE_FILES[*]} " =~ " ${filename} " ]]; then continue; fi
        if [[ " ${EXCLUDE_EXTENSIONS[*]} " =~ " ${extension,,} " ]]; then continue; fi
        if [[ "$filename" == _* || "$filename" == \._* ]]; then continue; fi
        if [[ "$input_path" == */_*/* || "$input_path" == */\._*/* ]]; then continue; fi

        parent_dir=$(dirname "$input_path")
        parent_base=$(basename "$parent_dir")
        if [[ "$parent_base" != "." && ("$parent_base" == _* || "$parent_base" == \._*) ]]; then continue; fi

        echo "===== $input_path =====" >> "$OUTPUT_FILE"
        if [ -n "$REGEX_FILTER_LINES" ]; then
            grep -vP "$REGEX_FILTER_LINES" "$input_path" >> "$OUTPUT_FILE"
        else
            cat "$input_path" >> "$OUTPUT_FILE"
        fi
        echo -e "\n\n" >> "$OUTPUT_FILE"

    elif [ -d "$input_path" ]; then
        find_args=()

        if [ ${#EXCLUDE_DIRS[@]} -gt 0 ]; then
            find_args+=("(")
            first=true
            for dir in "${EXCLUDE_DIRS[@]}"; do
                [ "$first" = false ] && find_args+=("-o")
                find_args+=(-name "$dir" -type d)
                first=false
            done
            find_args+=(")" -prune -o)
        fi

        find_args+=(-type f)
        for name in "${EXCLUDE_FILES[@]}"; do
            find_args+=(-not -name "$name")
        done
        for ext in "${EXCLUDE_EXTENSIONS[@]}"; do
            find_args+=(-not -iname "*.${ext}")
        done
        find_args+=(-not -name '_*' -not -name '\._*')
        find_args+=(-not -path '*/_*/*' -not -path '*/\._*/*')

        find "$input_path" "${find_args[@]}" -print0 | while IFS= read -r -d $'\0' file; do
            parent_dir=$(dirname "$file")
            parent_base=$(basename "$parent_dir")
            if [[ "$parent_base" != "." && ("$parent_base" == _* || "$parent_base" == \._*) ]]; then continue; fi

            echo "===== $file =====" >> "$OUTPUT_FILE"
            if [ -n "$REGEX_FILTER_LINES" ]; then
                grep -vP "$REGEX_FILTER_LINES" "$file" >> "$OUTPUT_FILE"
            else
                cat "$file" >> "$OUTPUT_FILE"
            fi
            echo -e "\n\n" >> "$OUTPUT_FILE"
        done
    fi
done

echo "Context successfully written to $OUTPUT_FILE"
