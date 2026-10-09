#!/usr/bin/env bash
# find-spec-dir.sh: Finds or creates the standard spec directory and generates a filename.
# Usage: find-spec-dir.sh "feature name"
# Outputs the full path for the spec file.

set -euo pipefail

feature_name="${1:-unnamed-feature}"

# Convert feature name to kebab-case filename
kebab_name=$(echo "$feature_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//')

# Get today's date
date_prefix=$(date +%Y-%m-%d)

# Determine spec directory
if [[ -d "docs/specs" ]]; then
  spec_dir="docs/specs"
elif [[ -d "docs" ]]; then
  spec_dir="docs/specs"
  mkdir -p "$spec_dir"
else
  spec_dir="docs/specs"
  mkdir -p "$spec_dir"
fi

# Generate filename
filename="${date_prefix}-${kebab_name}.md"
full_path="${spec_dir}/${filename}"

# Check for existing spec with same name (different date)
existing=$(find "$spec_dir" -name "*-${kebab_name}.md" 2>/dev/null | head -1)

cat <<EOF
{
  "spec_dir": "${spec_dir}",
  "filename": "${filename}",
  "full_path": "${full_path}",
  "existing_spec": "${existing:-none}"
}
EOF
