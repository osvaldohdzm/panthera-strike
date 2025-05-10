#!/bin/bash

# Ensure script stops on first error
set -e

git clean -fd

# Fetch the latest updates from the remote
echo "Fetching from origin..."
git fetch origin

# Switch to main branch
echo "Checking out main branch..."
git checkout main

# Merge changes from origin/dev into main
echo "Merging origin/dev into main..."
git merge origin/dev

echo "✅ main is now updated with the latest from origin/dev"
