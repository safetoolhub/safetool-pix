#!/usr/bin/env bash
# =============================================================================
# sync_to_public.sh
# Syncs the current state of safetool-pix-dev to the public safetool-pix repo.
# Creates a single clean commit (one per release) in the public repository.
#
# Usage:
#   bash dev-tools/sync_to_public.sh <version-tag>          # full release
#   bash dev-tools/sync_to_public.sh --dry-run <version-tag> # test only
#
# Example:
#   bash dev-tools/sync_to_public.sh v1.0.0
#   bash dev-tools/sync_to_public.sh --dry-run v1.1.0-beta
#
# Modes:
#   (default)   Pushes a release branch (based on public/main) to the public
#               repo, creates a PR against main, merges it, then tags the
#               merge commit. This respects branch protection rules.
#               Requires the gh CLI.
#   --dry-run   Pushes to a temporary branch (dry-run/<tag>) on the public
#               repo to trigger CI tests + all platform builds, but does NOT
#               touch main or create tags. The branch stays until you manually
#               delete it after verifying CI passed.
#
# Prerequisites:
#   - You are in the safetool-pix-dev repo root
#   - The public remote is configured: git remote add public https://github.com/safetoolhub/safetool-pix.git
#   - All changes are committed in the dev repo
#   - The version in config.py matches the tag you are passing
#   - gh CLI is installed and authenticated (for full releases)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PUBLIC_REMOTE="public"
PUBLIC_BRANCH="main"

# Files/dirs to EXCLUDE from the public repository
EXCLUDE=(
    "docs"
    ".agent"
    "AGENTS.md"
    ".github/copilot-instructions.md"
    ".github/prompts"
    "dev-tools/generate_icons.py"
    "dev-tools/sync_to_public.sh"
    ".vscode"
)

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
    shift
fi

if [ $# -ne 1 ]; then
    echo "Usage: $0 [--dry-run] <version-tag>"
    echo "Example: $0 v1.0.0"
    echo "         $0 --dry-run v1.0.0"
    exit 1
fi

TAG="$1"

# Validate tag format
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+ ]]; then
    echo "Error: Tag must start with 'v' followed by a version number (e.g. v1.0.0)"
    exit 1
fi

# Check we're in the repo root
if [ ! -f "config.py" ] || [ ! -f "main.py" ]; then
    echo "Error: Run this script from the safetool-pix-dev repo root."
    exit 1
fi

# Check the public remote exists
if ! git remote get-url "$PUBLIC_REMOTE" &>/dev/null; then
    echo "Error: Remote '$PUBLIC_REMOTE' not found."
    echo "Add it with: git remote add public https://github.com/safetoolhub/safetool-pix.git"
    exit 1
fi

# Check there are no uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

# Capture current branch BEFORE switching
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "main")

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "==========================================="
    echo "  DRY RUN — Testing release: $TAG"
    echo "==========================================="
    echo ""
else
    echo ""
    echo "==========================================="
    echo "  Syncing to public: $TAG"
    echo "==========================================="
    echo ""
fi

# ---------------------------------------------------------------------------
# Helper: merge CHANGELOG.md with historical entries from public repo
# ---------------------------------------------------------------------------
merge_changelog() {
    local backup_file="$1"
    if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
        if [ -f "CHANGELOG.md" ]; then
            python3 -c "
import sys, re

local_path = 'CHANGELOG.md'
backup_path = sys.argv[1]

with open(local_path, 'r') as f:
    local_content = f.read()
with open(backup_path, 'r') as f:
    backup_content = f.read()

def extract_versions(text):
    return set(re.findall(r'^##\s+.*?(\d+\.\d+\.\d+\S*)', text, re.MULTILINE))

local_versions = extract_versions(local_content)
backup_versions = extract_versions(backup_content)

missing = backup_versions - local_versions
if not missing:
    sys.exit(0)

sections = re.split(r'(?=^## )', backup_content, flags=re.MULTILINE)
missing_sections = []
for section in sections:
    for ver in missing:
        if ver in section:
            missing_sections.append(section.rstrip())
            break

if missing_sections:
    with open(local_path, 'a') as f:
        f.write('\n\n')
        f.write('\n\n'.join(missing_sections))
        f.write('\n')
" "$backup_file"
            echo "      ✓ CHANGELOG.md merged with historical entries."
        else
            cp "$backup_file" CHANGELOG.md
            echo "      ✓ CHANGELOG.md restored from public repo."
        fi
        git add CHANGELOG.md
        rm -f "$backup_file"
    fi
}

COMMIT_MSG="Release $TAG

SafeTool Pix $TAG — Privacy-first photo & video management.
100% local processing, no cloud, no telemetry.

Full changelog: https://github.com/safetoolhub/safetool-pix/blob/main/CHANGELOG.md"

# Save the dev commit so we can restore files from it later
DEV_COMMIT=$(git rev-parse HEAD)

# ---------------------------------------------------------------------------
# Preserve CHANGELOG.md from the public repo (if it exists)
# ---------------------------------------------------------------------------
CHANGELOG_BACKUP=""
echo "[0] Fetching public repo..."
git fetch "$PUBLIC_REMOTE" "$PUBLIC_BRANCH" --depth=1 2>/dev/null || true
if git show "$PUBLIC_REMOTE/$PUBLIC_BRANCH:CHANGELOG.md" &>/dev/null; then
    CHANGELOG_BACKUP=$(mktemp)
    git show "$PUBLIC_REMOTE/$PUBLIC_BRANCH:CHANGELOG.md" > "$CHANGELOG_BACKUP"
    echo "    ✓ Existing CHANGELOG.md saved for preservation."
else
    echo "    No existing CHANGELOG.md found in public repo (first release?)."
fi

# ---------------------------------------------------------------------------
# Dry-run vs full release — different branch strategies
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
    # -----------------------------------------------------------------------
    # DRY RUN: orphan branch (no PR needed, just push to trigger CI)
    # -----------------------------------------------------------------------
    ORPHAN_BRANCH="public-release-$(date +%s)"

    echo "[1/5] Creating orphan branch '$ORPHAN_BRANCH'..."
    git checkout --orphan "$ORPHAN_BRANCH"

    echo "[2/5] Removing excluded files from public snapshot..."
    for item in "${EXCLUDE[@]}"; do
        if [ -e "$item" ]; then
            git rm -rf --quiet --ignore-unmatch "$item"
            echo "      Excluded: $item"
        fi
    done

    merge_changelog "$CHANGELOG_BACKUP"

    echo "[3/5] Creating release commit..."
    git add -A
    git commit -m "$COMMIT_MSG"

    DRY_RUN_BRANCH="dry-run/${TAG}"

    echo "[4/5] Pushing to temporary branch '$DRY_RUN_BRANCH' on public remote..."
    git push --force "$PUBLIC_REMOTE" "$ORPHAN_BRANCH:refs/heads/$DRY_RUN_BRANCH"

    echo "[5/5] Done. CI will run tests + all platform builds on the public repo."

    # Cleanup
    git checkout "$CURRENT_BRANCH"
    git branch -D "$ORPHAN_BRANCH" 2>/dev/null || true

    echo ""
    echo "✓ Dry run complete."
    echo "  Branch '$DRY_RUN_BRANCH' pushed to public repo."
    echo "  CI will run: tests → Linux/Win/macOS/Flatpak builds (no release created)."
    echo ""
    echo "  Check progress: https://github.com/safetoolhub/safetool-pix/actions"
    echo ""
    echo "  Once verified, delete the remote branch with:"
    echo "    git push $PUBLIC_REMOTE --delete $DRY_RUN_BRANCH"
    echo ""
else
    # -------------------------------------------------------------------
    # FULL RELEASE: branch from public/main so there is shared history,
    # replace all content with the dev snapshot, create PR, merge, tag.
    # -------------------------------------------------------------------
    LOCAL_RELEASE_BRANCH="public-release-$(date +%s)"
    RELEASE_BRANCH="release/${TAG}"
    PUBLIC_REPO_SLUG="safetoolhub/safetool-pix"

    # Verify gh CLI is available
    if ! command -v gh &>/dev/null; then
        echo "Error: GitHub CLI (gh) is required for full releases."
        echo "Install it: https://cli.github.com/"
        exit 1
    fi

    echo "[1/7] Creating release branch from $PUBLIC_REMOTE/$PUBLIC_BRANCH..."
    git checkout -b "$LOCAL_RELEASE_BRANCH" "$PUBLIC_REMOTE/$PUBLIC_BRANCH"

    echo "[2/7] Replacing content with dev snapshot..."
    # Remove all existing files from the public branch
    git rm -rf --quiet . 2>/dev/null || true
    # Restore all files from the dev commit
    git checkout "$DEV_COMMIT" -- .

    echo "[3/7] Removing excluded files..."
    for item in "${EXCLUDE[@]}"; do
        if [ -e "$item" ]; then
            git rm -rf --quiet --ignore-unmatch "$item"
            echo "      Excluded: $item"
        fi
    done

    merge_changelog "$CHANGELOG_BACKUP"

    echo "[4/7] Creating release commit..."
    git add -A
    git commit -m "$COMMIT_MSG"

    echo "[5/7] Pushing release branch '$RELEASE_BRANCH' to public remote..."
    git push --force "$PUBLIC_REMOTE" "$LOCAL_RELEASE_BRANCH:refs/heads/$RELEASE_BRANCH"

    echo "[6/7] Creating and merging pull request on $PUBLIC_REPO_SLUG..."
    PR_URL=$(gh pr create \
        --repo "$PUBLIC_REPO_SLUG" \
        --base "$PUBLIC_BRANCH" \
        --head "$RELEASE_BRANCH" \
        --title "Release $TAG" \
        --body "$COMMIT_MSG")
    echo "      ✓ PR created: $PR_URL"

    gh pr merge "$PR_URL" \
        --repo "$PUBLIC_REPO_SLUG" \
        --merge \
        --admin \
        --delete-branch \
        --subject "Release $TAG" \
        --body "$COMMIT_MSG"
    echo "      ✓ PR merged."

    echo "[7/7] Creating and pushing annotated tag $TAG..."
    # Fetch the merged main so the tag points to the merge commit
    git fetch "$PUBLIC_REMOTE" "$PUBLIC_BRANCH"
    git tag -f -a "$TAG" "$PUBLIC_REMOTE/$PUBLIC_BRANCH" -m "SafeTool Pix $TAG"
    git push --force "$PUBLIC_REMOTE" "$TAG"

    # Cleanup
    git checkout "$CURRENT_BRANCH"
    git branch -D "$LOCAL_RELEASE_BRANCH" 2>/dev/null || true

    echo ""
    echo "✓ Public repository updated: https://github.com/$PUBLIC_REPO_SLUG"
    echo ""
    echo "The release workflow will trigger automatically on the pushed tag."
    echo "Go to GitHub → Releases to review and publish the draft release."
    echo ""
fi

echo "Returned to '$CURRENT_BRANCH'. Dev repository is unchanged."
