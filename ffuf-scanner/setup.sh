#!/usr/bin/env bash
# setup.sh — Download and install ffuf v2.2.1 (Linux amd64) into this directory.
# Usage: bash setup.sh
set -euo pipefail

FFUF_VERSION="2.2.1"
ARCHIVE="ffuf_${FFUF_VERSION}_linux_amd64.tar.gz"
BASE_URL="https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}"
CHECKSUMS_FILE="ffuf_${FFUF_VERSION}_checksums.txt"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bin"

echo "==> Creating install directory: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

echo "==> Downloading ffuf v${FFUF_VERSION} ..."
curl -fsSL "${BASE_URL}/${ARCHIVE}" -o "/tmp/${ARCHIVE}"

echo "==> Downloading checksums ..."
curl -fsSL "${BASE_URL}/${CHECKSUMS_FILE}" -o "/tmp/${CHECKSUMS_FILE}"

echo "==> Verifying checksum ..."
cd /tmp
grep "${ARCHIVE}" "${CHECKSUMS_FILE}" | sha256sum --check --status
echo "    Checksum OK"

echo "==> Extracting binary ..."
tar -xzf "/tmp/${ARCHIVE}" -C "${INSTALL_DIR}" ffuf

chmod +x "${INSTALL_DIR}/ffuf"

echo "==> ffuf installed to ${INSTALL_DIR}/ffuf"
echo "    Run: ${INSTALL_DIR}/ffuf -h"
echo ""
echo "==> Cleaning up temp files ..."
rm -f "/tmp/${ARCHIVE}" "/tmp/${CHECKSUMS_FILE}"

echo "Done."
