#!/bin/bash
# Script to sync changes to GitHub while excluding sensitive files

set -e  # Exit on error

echo "🔄 Syncing to GitHub branch..."

# Files to exclude from GitHub
EXCLUDE_FILES=".env.gpg test-defaults.env push-to-github.sh"

# Save current branch
CURRENT_BRANCH=$(git branch --show-current)

# Ensure we're on main branch
git checkout main

# Create or switch to github branch
git checkout -B github

# Reset github branch to match main
git reset --hard main

# Remove excluded files from the index
for file in $EXCLUDE_FILES; do
    if git ls-files --error-unmatch "$file" 2>/dev/null; then
        echo "🚫 Removing $file from github branch"
        git rm --cached "$file" 2>/dev/null || true
    fi
done

# Commit the removal if there are changes
if ! git diff --cached --quiet; then
    git commit -m "Remove sensitive files for GitHub"
fi

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push -f upstream github:main

# Return to original branch
git checkout "$CURRENT_BRANCH"

echo "✅ Successfully pushed to GitHub (without sensitive files)"
echo "📍 You are back on branch: $CURRENT_BRANCH"