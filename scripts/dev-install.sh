#!/usr/bin/env bash
#
# Create a symlink from Alfred's workflow directory to the repo source,
# enabling live development without rebuilding.
#
# Usage: ./scripts/dev-install.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALFRED_PREFS_DIR="${HOME}/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows"
BUNDLE_ID="com.ayapejian.alfred-homeassistant"
LINK_NAME="user.workflow.${BUNDLE_ID}"
LINK_PATH="${ALFRED_PREFS_DIR}/${LINK_NAME}"

# Verify Alfred preferences directory exists
if [ ! -d "${ALFRED_PREFS_DIR}" ]; then
  echo "Error: Alfred workflows directory not found at:"
  echo "  ${ALFRED_PREFS_DIR}"
  echo ""
  echo "Make sure Alfred 5 is installed and has been launched at least once."
  exit 1
fi

# Check for existing symlink or directory
if [ -L "${LINK_PATH}" ]; then
  EXISTING_TARGET=$(readlink "${LINK_PATH}")
  if [ "${EXISTING_TARGET}" = "${REPO_ROOT}" ]; then
    echo "Already linked: ${LINK_PATH} -> ${REPO_ROOT}"
    exit 0
  fi
  echo "Updating existing symlink..."
  rm "${LINK_PATH}"
elif [ -d "${LINK_PATH}" ]; then
  echo "Error: A directory (not symlink) already exists at:"
  echo "  ${LINK_PATH}"
  echo ""
  echo "This may be an installed copy of the workflow."
  echo "Remove it first, then re-run this script."
  exit 1
fi

ln -s "${REPO_ROOT}" "${LINK_PATH}"
echo "Linked: ${LINK_PATH} -> ${REPO_ROOT}"
echo ""
echo "The workflow should now appear in Alfred Preferences."
echo "Code changes will be reflected immediately without rebuilding."
echo ""
echo "To configure, set HA_URL and HA_TOKEN in:"
echo "  Alfred Preferences > Workflows > Home Assistant > Configure..."
