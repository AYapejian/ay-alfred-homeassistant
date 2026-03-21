#!/usr/bin/env bash
#
# Build the .alfredworkflow artifact.
# Usage: ./scripts/build.sh [--output PATH]
#
# Produces: dist/ay-alfred-homeassistant.alfredworkflow
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
STAGING_DIR="${DIST_DIR}/staging"
OUTPUT="${1:-${DIST_DIR}/ay-alfred-homeassistant.alfredworkflow}"

echo "==> Cleaning previous build..."
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}" "$(dirname "${OUTPUT}")"

echo "==> Copying workflow resources..."
cp "${REPO_ROOT}/workflow/info.plist" "${STAGING_DIR}/"
cp "${REPO_ROOT}/workflow/icon.png" "${STAGING_DIR}/"

# Copy domain icons if they exist
if [ -d "${REPO_ROOT}/workflow/icons" ] && [ "$(ls -A "${REPO_ROOT}/workflow/icons" 2>/dev/null)" ]; then
  cp -r "${REPO_ROOT}/workflow/icons" "${STAGING_DIR}/"
fi

echo "==> Copying Python source..."
cp -r "${REPO_ROOT}/src/ha_workflow" "${STAGING_DIR}/ha_workflow"

# Remove __pycache__ and .pyc files from the copy
find "${STAGING_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${STAGING_DIR}" -name "*.pyc" -delete 2>/dev/null || true

# Copy vendored libraries if they exist
if [ -d "${REPO_ROOT}/lib" ] && [ "$(ls -A "${REPO_ROOT}/lib" 2>/dev/null)" ]; then
  echo "==> Copying vendored libraries..."
  cp -r "${REPO_ROOT}/lib" "${STAGING_DIR}/lib"
fi

echo "==> Packaging .alfredworkflow..."
(cd "${STAGING_DIR}" && zip -qr "${OUTPUT}" .)

echo "==> Cleaning staging directory..."
rm -rf "${STAGING_DIR}"

FILESIZE=$(stat -f%z "${OUTPUT}" 2>/dev/null || stat --printf="%s" "${OUTPUT}" 2>/dev/null)
echo "==> Built: ${OUTPUT} (${FILESIZE} bytes)"
