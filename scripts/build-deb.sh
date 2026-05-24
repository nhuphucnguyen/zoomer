#!/usr/bin/env bash
set -euo pipefail

PACKAGE_NAME="boomer-codex"
VERSION="${VERSION:-0.1.0}"
ARCHITECTURE="${ARCHITECTURE:-all}"
MAINTAINER="${MAINTAINER:-Boomer Codex Maintainers <maintainers@example.com>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build/deb"
STAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}"
OUTPUT_DIR="${ROOT_DIR}/dist"
OUTPUT_FILE="${OUTPUT_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}.deb"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

require_file() {
    if [[ ! -f "$1" ]]; then
        echo "Missing required file: $1" >&2
        exit 1
    fi
}

require_command dpkg-deb

require_file "${ROOT_DIR}/src/boomer.py"
require_file "${ROOT_DIR}/src/tray.py"
require_file "${ROOT_DIR}/src/config.py"
require_file "${ROOT_DIR}/src/navigation.py"
require_file "${ROOT_DIR}/src/screenshot.py"
require_file "${ROOT_DIR}/src/frag.glsl"
require_file "${ROOT_DIR}/src/vert.glsl"

rm -rf "${STAGE_DIR}"
mkdir -p \
    "${STAGE_DIR}/DEBIAN" \
    "${STAGE_DIR}/usr/bin" \
    "${STAGE_DIR}/usr/lib/${PACKAGE_NAME}" \
    "${STAGE_DIR}/usr/share/applications" \
    "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}" \
    "${STAGE_DIR}/usr/share/icons/hicolor/scalable/apps" \
    "${OUTPUT_DIR}"

install -m 0644 \
    "${ROOT_DIR}/src/boomer.py" \
    "${ROOT_DIR}/src/config.py" \
    "${ROOT_DIR}/src/navigation.py" \
    "${ROOT_DIR}/src/screenshot.py" \
    "${ROOT_DIR}/src/tray.py" \
    "${ROOT_DIR}/src/frag.glsl" \
    "${ROOT_DIR}/src/vert.glsl" \
    "${STAGE_DIR}/usr/lib/${PACKAGE_NAME}/"

install -m 0644 "${ROOT_DIR}/README.md" "${STAGE_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md"

cat >"${STAGE_DIR}/usr/bin/boomer" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/boomer-codex/boomer.py "$@"
EOF

cat >"${STAGE_DIR}/usr/bin/boomer-tray" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/boomer-codex/tray.py "$@"
EOF

chmod 0755 "${STAGE_DIR}/usr/bin/boomer" "${STAGE_DIR}/usr/bin/boomer-tray"

cat >"${STAGE_DIR}/usr/share/applications/boomer-codex.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Boomer Codex
Comment=Screen zoomer and screenshot inspection tool
Exec=boomer-tray
Icon=boomer-codex
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=false
EOF

cat >"${STAGE_DIR}/usr/share/icons/hicolor/scalable/apps/boomer-codex.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="27" fill="#242424"/>
  <circle cx="29" cy="29" r="13" fill="none" stroke="#ffffff" stroke-width="6"/>
  <path d="M39 39 L53 53" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>
</svg>
EOF

cat >"${STAGE_DIR}/DEBIAN/control" <<EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCHITECTURE}
Maintainer: ${MAINTAINER}
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, python3-dbus, python3-numpy, python3-pil, python3-opengl, python3-pynput, python3-tk
Recommends: grim | scrot
Description: Screen zoomer for GNOME
 Boomer Codex captures the current screen and opens it in an interactive zoom
 window. It also includes a background tray launcher for quick captures.
EOF

cat >"${STAGE_DIR}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

exit 0
EOF

cat >"${STAGE_DIR}/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

exit 0
EOF

chmod 0755 "${STAGE_DIR}/DEBIAN/postinst" "${STAGE_DIR}/DEBIAN/postrm"

find "${STAGE_DIR}" -type d -exec chmod 0755 {} +
find "${STAGE_DIR}" -type f ! -path '*/DEBIAN/postinst' ! -path '*/DEBIAN/postrm' ! -path '*/usr/bin/boomer' ! -path '*/usr/bin/boomer-tray' -exec chmod 0644 {} +

dpkg-deb --build --root-owner-group "${STAGE_DIR}" "${OUTPUT_FILE}"

echo "Built ${OUTPUT_FILE}"
echo "Install with: sudo apt install ${OUTPUT_FILE}"