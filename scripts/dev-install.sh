#!/usr/bin/env bash
#
# Create a symlink from Alfred's workflow directory to the repo's workflow/
# directory, enabling live development without rebuilding.
#
# Also creates a symlink inside workflow/ pointing to the Python source so
# that Alfred can import ha_workflow when running scripts.
#
# Usage: ./scripts/dev-install.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKFLOW_DIR="${REPO_ROOT}/workflow"
BUNDLE_ID="com.ayapejian.alfred-homeassistant"
LINK_NAME="user.workflow.${BUNDLE_ID}"

# Detect Alfred preferences directory.  Alfred 5 supports a custom sync
# folder via the "syncfolder" preference — check that first, then fall
# back to the default local location.
SYNC_FOLDER=$(defaults read com.runningwithcrayons.Alfred-Preferences syncfolder 2>/dev/null || true)

if [ -n "${SYNC_FOLDER}" ]; then
  # Expand leading ~ to $HOME
  SYNC_FOLDER="${SYNC_FOLDER/#\~/$HOME}"
  ALFRED_PREFS_DIR="${SYNC_FOLDER}/Alfred.alfredpreferences/workflows"
else
  ALFRED_PREFS_DIR="${HOME}/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows"
fi

LINK_PATH="${ALFRED_PREFS_DIR}/${LINK_NAME}"

# Verify Alfred preferences directory exists
if [ ! -d "${ALFRED_PREFS_DIR}" ]; then
  echo "Error: Alfred workflows directory not found at:"
  echo "  ${ALFRED_PREFS_DIR}"
  echo ""
  echo "Make sure Alfred 5 is installed and has been launched at least once."
  exit 1
fi

# --- Step 1: Symlink ha_workflow source into workflow/ for dev ---
HA_SRC_LINK="${WORKFLOW_DIR}/ha_workflow"
if [ -L "${HA_SRC_LINK}" ]; then
  echo "Source symlink exists: ${HA_SRC_LINK}"
elif [ -d "${HA_SRC_LINK}" ]; then
  echo "Warning: ${HA_SRC_LINK} is a real directory, skipping symlink."
else
  ln -s "${REPO_ROOT}/src/ha_workflow" "${HA_SRC_LINK}"
  echo "Created source symlink: workflow/ha_workflow -> ../src/ha_workflow"
fi

# --- Step 2: Symlink workflow/ into Alfred's preferences ---
if [ -L "${LINK_PATH}" ]; then
  EXISTING_TARGET=$(readlink "${LINK_PATH}")
  if [ "${EXISTING_TARGET}" = "${WORKFLOW_DIR}" ]; then
    echo "Already linked: ${LINK_PATH} -> ${WORKFLOW_DIR}"
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

ln -s "${WORKFLOW_DIR}" "${LINK_PATH}"
echo "Linked: ${LINK_PATH} -> ${WORKFLOW_DIR}"
echo ""
echo "The workflow should now appear in Alfred Preferences."
echo "Code changes will be reflected immediately without rebuilding."
echo ""
echo "To configure, set HA_URL and HA_TOKEN in:"
echo "  Alfred Preferences > Workflows > Home Assistant > Configure..."
