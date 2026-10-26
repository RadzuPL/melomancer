#!/usr/bin/env bash
# Prints the version (without the leading "v") to build for the current commit.
#
#   HEAD already carries a vX.Y.Z tag  -> that version (re-runs do not burn numbers)
#   no vX.Y.Z tag exists yet           -> 0.1.0
#   otherwise the newest tag, bumped according to the commit messages since it:
#       "BREAKING CHANGE" or "type!:"  -> major
#       "feat:" / "feat(scope):"       -> minor
#       anything else                  -> patch
#
# NO_BUMP=1 prints the newest existing version without bumping (used by the weekly rebuild,
# which only refreshes the image and must not create a release).
set -euo pipefail

pattern='v[0-9]*.[0-9]*.[0-9]*'

newest_tag() { git tag --list "$pattern" --sort=-v:refname | head -n1 || true; }

at_head=$(git tag --points-at HEAD --list "$pattern" --sort=-v:refname | head -n1 || true)
if [ -n "$at_head" ]; then
  echo "${at_head#v}"
  exit 0
fi

last=$(newest_tag)
if [ -z "$last" ]; then
  echo "0.1.0"
  exit 0
fi

if [ "${NO_BUMP:-0}" = "1" ]; then
  echo "${last#v}"
  exit 0
fi

IFS=. read -r major minor patch <<<"${last#v}"
log=$(git log --format=%B "${last}..HEAD")

if grep -Eq 'BREAKING CHANGE|^[a-z]+(\([^)]*\))?!:' <<<"$log"; then
  major=$((major + 1)); minor=0; patch=0
elif grep -Eq '^feat(\([^)]*\))?:' <<<"$log"; then
  minor=$((minor + 1)); patch=0
else
  patch=$((patch + 1))
fi

echo "${major}.${minor}.${patch}"
