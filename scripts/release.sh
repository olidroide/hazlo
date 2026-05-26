#!/usr/bin/env bash
set -euo pipefail

VERSION_FILE="hazlo/__init__.py"
TAG=$(date +%Y%m%d%H%M)

sed -i.bak "s/__version__ = .*/__version__ = \"$TAG\"/" "$VERSION_FILE"
rm -f "${VERSION_FILE}.bak"

git add "$VERSION_FILE"
git commit -m "release: $TAG"
git tag "$TAG"

echo "Released: $TAG"
echo "Push with: git push && git push origin $TAG"