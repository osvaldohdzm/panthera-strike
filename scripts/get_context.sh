#!/bin/bash

# --- Configuration ---
# Output file where the context will be written
OUTPUT_FILE="code_context.txt"

# Regex to filter out lines from the content of selected files:
# Matches lines starting with '#' (optional leading spaces) UNLESS '.py' appears later on the same line.
# Lines matching this regex will be REMOVED from the output.
REGEX_FILTER_LINES='^\s*#(?!.*\.py).*'

# File extensions to exclude entirely (case-insensitive matching for find)
EXCLUDE_EXTENSIONS=(
  "css" "sh" "html" "gitignore" "md" "txt" "json" "xml" "yaml" "yml" "toml" # Common non-code or config
  "jpg" "jpeg" "png" "gif" "webp" "bmp" # Images
  "mp4" "mkv" "avi" "mov" "flv" "webm" # Videos
  "mp3" "wav" "ogg" "flac" "aac" # Audio
  "ico" "svg" "pdf" "ttf" "woff" "woff2" "eot" # Assets and documents
  "zip" "tar" "gz" "rar" "7z" "bz2" "xz" # Archives
  "pyc" "pyd" "pyo" "whl" "egg" # Python compiled/package files
  "lock" "sum" # Dependency lock files
  "bin" "exe" "dll" "so" "o" "a" "lib" "class" "jar" "war" "ear" # Compiled objects/binaries
  "DS_Store" # macOS specific
  "log" # Log files
  "bak" "swp" "swo" # Backup/swap files
)

# Directory names to exclude entirely (find will prune these)
EXCLUDE_DIRS=(
  ".git" "node_modules" "__pycache__" ".venv" "env" "venv" "ENV" ".env"
  "build" "dist" "results" "scan_results" "target" "out" "bin" "obj"
  ".idea" ".vscode" ".settings" ".project" ".classpath" # IDE specific
  ".tox" ".nox" ".pytest_cache" ".eggs" ".mypy_cache" # Python tooling
  ".scrapy" ".hypothesis" "instance" ".webassets-cache"
  "docs" "doc" "site" "_site" "javadoc" # Documentation
  "testdata" "fixtures" "examples" "samples" # Test/example data (can be project specific)
  "migrations" # Database migrations (often verbose)
  "vendor" "third_party" "external" # Vendored libraries
  "coverage" # Coverage reports
  "logs" # Log directories
  "temp" "tmp" # Temporary directories
)

# Specific file basenames to exclude entirely
EXCLUDE_FILES=(
  # The output file itself will be added automatically later
  "tools_config.json" "panthera.db" # User's original exclusions
  "MANIFEST.in" "setup.cfg" "setup.py" # Python packaging (setup.py might be desired by some)
  ".DS_Store" "Thumbs.db"
  "Jenkinsfile" "Dockerfile" "docker-compose.yml" # CI/CD and Docker (project specific if desired)
  "Makefile" "pom.xml" "build.gradle" # Build system files (project specific)
  "README" "LICENSE" "CONTRIBUTING" # Common repo files often with extensions like .md
)
# --- End Configuration ---

# Determine directories to scan: use provided arguments or defaults
if [ "$#" -gt 0 ]; then
    DIRS_TO_SCAN=("$@")
else
    # Default directories if none are provided
    DIRS_TO_SCAN=("static" "templates" "scanner" "utils" ".") # Added current dir as an example
fi

# Ensure the output file itself is in the exclusion list to prevent self-inclusion
output_file_basename=$(basename "$OUTPUT_FILE")
is_output_excluded=false
for excluded_file in "${EXCLUDE_FILES[@]}"; do
    if [[ "$excluded_file" == "$output_file_basename" ]]; then
        is_output_excluded=true
        break
    fi
done
if [ "$is_output_excluded" = false ]; then
    EXCLUDE_FILES+=("$output_file_basename")
fi

# Truncate the output file at the beginning of the script execution
echo -n > "$OUTPUT_FILE" # More portable way to truncate

# --- Main Processing Loop ---
for scan_dir in "${DIRS_TO_SCAN[@]}"; do
    # Normalize scan_dir path (remove trailing slash if any)
    scan_dir_normalized="${scan_dir%/}"
    if [ ! -d "$scan_dir_normalized" ]; then
        echo "Warning: Directory '$scan_dir_normalized' does not exist. Skipping." >&2
        continue
    fi

    # Build find command arguments
    find_args=()

    # 1. Prune excluded directories (by name)
    if [ ${#EXCLUDE_DIRS[@]} -gt 0 ]; then
        find_args+=("(")
        first_dir_prune=true
        for dir_name in "${EXCLUDE_DIRS[@]}"; do
            if [ "$first_dir_prune" = false ]; then
                find_args+=("-o")
            fi
            # Match directory by name. This will apply to any directory found.
            find_args+=(-name "$dir_name" -type d)
            first_dir_prune=false
        done
        find_args+=(")")
        find_args+=("-prune" "-o") # If pruned, don't process further; else, continue.
    fi

    # 2. Define conditions for files to be selected (these apply to non-pruned paths)
    find_args+=("-type" "f") # Select only regular files

    # Exclude specific filenames (basenames)
    for file_name in "${EXCLUDE_FILES[@]}"; do
        find_args+=(-not -name "$file_name")
    done

    # Exclude specific extensions (case-insensitive)
    for ext in "${EXCLUDE_EXTENSIONS[@]}"; do
        find_args+=(-not -iname "*.${ext}")
    done

    # Filter files/directories starting with '_' or '._' based on original script's logic
    # - Exclude files whose name starts with '_' or '._'
    find_args+=(-not -name '_*' -not -name '\._*')
    # - Exclude files if any part of their path (a directory component) starts with '_' or '._'
    #   e.g., `somedir/_subdir/file.txt` or `somedir/subdir/._another/file.txt`
    find_args+=(-not -path '*/_*/*' -not -path '*/\._*/*')

    # Execute find and process each found file
    # Using -print0 and read -d $'\0' for robust handling of filenames
    # find "$scan_dir_normalized" "${find_args[@]}" -print0
    # The above line can be used for debugging the find command itself.

    find "$scan_dir_normalized" "${find_args[@]}" -print0 | while IFS= read -r -d $'\0' file_path; do
        # Additional check for fidelity with original script's `dirname` logic:
        # If a file's immediate parent directory's name starts with `_` or `._`, skip it.
        # This is particularly for cases like `_top_level_dir_in_DIRS_TO_SCAN/file.txt`,
        # which the `find -not -path '*/_*/*'` might not catch if `_top_level_dir_in_DIRS_TO_SCAN`
        # is the starting point of the find operation for that path.
        parent_dir_of_file=$(dirname "$file_path")
        basename_of_parent_dir=$(basename "$parent_dir_of_file")

        if [[ "$basename_of_parent_dir" != "." && ("$basename_of_parent_dir" == _* || "$basename_of_parent_dir" == \._*) ]]; then
            # echo "Debug: Skipping (parent dir basename rule): $file_path (parent basename: $basename_of_parent_dir)" >&2
            continue
        fi
        
        # All filters passed, add file content to the output file
        echo "===== $file_path =====" >> "$OUTPUT_FILE"
        if [ -n "$REGEX_FILTER_LINES" ]; then
            # Filter out lines matching the regex before appending to output
            grep -vP "$REGEX_FILTER_LINES" "$file_path" >> "$OUTPUT_FILE" # CAMBIO: -vE a -vP
        else
            cat "$file_path" >> "$OUTPUT_FILE"
        fi
        echo -e "\n\n" >> "$OUTPUT_FILE"
    done
done

echo "Context successfully written to $OUTPUT_FILE"