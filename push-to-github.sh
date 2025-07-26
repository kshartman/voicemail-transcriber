#!/bin/bash
# Script to sync changes to GitHub while excluding sensitive files

set -e  # Exit on error

echo "🔄 Syncing to GitHub..."

# Check if 'upstream' remote exists (GitHub)
if ! git remote get-url upstream >/dev/null 2>&1; then
    echo "❌ Error: 'upstream' remote not configured"
    echo "Please add GitHub remote with: git remote add upstream git@github.com:YOUR_USERNAME/voicemail-transcriber.git"
    exit 1
fi

# Files to exclude from GitHub
EXCLUDE_FILES=".env.gpg test-defaults.env push-to-github.sh"

# Save current branch
CURRENT_BRANCH=$(git branch --show-current)

# Create a temporary directory and move sensitive files there
TEMP_DIR=$(mktemp -d)
echo "📦 Moving sensitive files to temp directory..."
for file in $EXCLUDE_FILES; do
    if [ -f "$file" ]; then
        cp "$file" "$TEMP_DIR/" 2>/dev/null || true
    fi
done

# Create or switch to github branch
git checkout -B github-temp

# Reset github-temp branch to match current branch
git reset --hard "$CURRENT_BRANCH"

# Remove excluded files from the working directory and index
for file in $EXCLUDE_FILES; do
    if [ -f "$file" ]; then
        echo "🚫 Removing $file from GitHub push"
        rm -f "$file"
    fi
    git rm --cached "$file" 2>/dev/null || true
done

# Commit the removal if there are changes
if ! git diff --cached --quiet; then
    git commit -m "Remove sensitive files for GitHub"
fi

# Push to GitHub (upstream remote)
echo "📤 Pushing to GitHub (upstream)..."
git push -f upstream github-temp:main

# Return to original branch
git checkout "$CURRENT_BRANCH"

# Restore sensitive files from temp directory
echo "📥 Restoring sensitive files..."
for file in $EXCLUDE_FILES; do
    if [ -f "$TEMP_DIR/$file" ]; then
        cp "$TEMP_DIR/$file" . 2>/dev/null || true
    fi
done

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "✅ Successfully pushed to GitHub (without sensitive files)"
echo "📍 You are back on branch: $CURRENT_BRANCH"