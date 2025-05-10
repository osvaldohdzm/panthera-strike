#!/bin/bash

# Output file
OUTPUT_FILE="code_context.txt"

# Use provided directories if any, else use defaults
if [ "$#" -gt 0 ]; then
    DIRS=("$@")
else
    DIRS=("static" "templates" "scanner" "utils")
fi

# Truncate the output file if it exists
> "$OUTPUT_FILE"

# Loop over each directory
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Find all files excluding those in subdirs or with names starting with "_"
        find "$dir" -type f \
        | grep -v '/_' \
        | grep -v '/\._' \
        | while read -r file; do
            filename=$(basename "$file")
            dirname=$(basename "$(dirname "$file")")

            # Skip if file or parent dir starts with "_"
            if [[ "$filename" != _* && "$dirname" != _* ]]; then
                echo "===== $file =====" >> "$OUTPUT_FILE"
                cat "$file" >> "$OUTPUT_FILE"
                echo -e "\n\n" >> "$OUTPUT_FILE"
            fi
        done
    else
        echo "Directory '$dir' does not exist."
    fi
done
