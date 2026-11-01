#!/usr/bin/env bash
set -e

echo "========================================================"
echo "       TRUTHMAP AI — One-Click GitHub Uploader"
echo "========================================================"

if ! command -v git &> /dev/null; then
    echo "[ERROR] Git is not installed."
    exit 1
fi

if [ ! -d ".git" ]; then
    echo "Initializing git repository on branch main..."
    git init -b main
fi

git add .
git status --short

read -p "Enter commit message (default: 'feat: update TRUTHMAP AI platform'): " COMMIT_MSG
COMMIT_MSG=${COMMIT_MSG:-"feat: update TRUTHMAP AI platform"}

git commit -m "$COMMIT_MSG" || true

if git remote get-url origin &> /dev/null; then
    echo "Current remote: $(git remote get-url origin)"
else
    read -p "Enter your GitHub repository URL (e.g. https://github.com/username/truthmap-ai.git): " REPO_URL
    git remote add origin "$REPO_URL"
fi

git branch -M main
git push -u origin main
echo "[SUCCESS] Pushed to GitHub successfully!"
