#!/bin/bash

# Output file
OUTPUT_FILE="code_context.txt"

# Directories to search
DIRS=("static" "templates")

# Truncate the output file if it exists
> "$OUTPUT_FILE"

# Loop over each directory
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Find all files and append their contents
        find "$dir" -type f | while read -r file; do
            echo "===== $file =====" >> "$OUTPUT_FILE"
            cat "$file" >> "$OUTPUT_FILE"
            echo -e "\n\n" >> "$OUTPUT_FILE"
        done
    else
        echo "Directory '$dir' does not exist."
    fi
done
