#!/bin/bash
set -e

# Configuration
APP_NAME="cogny"
VERSION="1.0.2"
ARCH="amd64"
DEB_NAME="${APP_NAME}_${VERSION}_${ARCH}"
BUILD_DIR="build_deb"
INSTALL_DIR="/opt/$APP_NAME"
DESKTOP_FILE="cogny.desktop"
ICON_FILE="assets/logo.png"

echo "=== Iniciando creación del paquete .deb para $APP_NAME ==="

# Check dependencies
echo "-> Verificando dependencias..."
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 no está instalado."; exit 1; }
command -v dpkg-deb >/dev/null 2>&1 || { echo "Error: dpkg-deb no está instalado."; exit 1; }

# Create virtual environment for build if it doesn't exist
if [ ! -d "venv_build" ]; then
    echo "-> Creando entorno virtual temporal..."
    python3 -m venv venv_build
fi

source venv_build/bin/activate

# Install requirements and pyinstaller
echo "-> Instalando librerías y PyInstaller..."
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo "-> Limpiando builds anteriores..."
rm -rf build dist "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build with PyInstaller
echo "-> Compilando ejecutable con PyInstaller..."
# --onedir: Create a directory containing the executable (faster startup than --onefile)
# --windowed: No console window
# --name: Name of the executable
# --add-data: Include assets
pyinstaller --noconfirm --onedir --windowed --clean \
    --name "$APP_NAME" \
    --add-data "assets:assets" \
    --hidden-import "PySide6" \
    main.py

# Structure for .deb
echo "-> Estructurando el paquete .deb..."
# Create directory structure
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR$INSTALL_DIR"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy executable and files to /opt/cogny
echo "-> Copiando archivos de la aplicación..."
cp -r "dist/$APP_NAME/"* "$BUILD_DIR$INSTALL_DIR/"

# Create control file
echo "-> Creando archivo de control..."
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Mario <mario@example.com>
Depends: libc6, libgl1
Description: Hierarchical Note Taking App
 Cogny is a modern note-taking application designed for efficiency.
 helping you organize your thoughts hierarchically.
EOF
# Note: PyInstaller bundles Python, so we don't strictly need python3 dependency,
# but system libs like libc6 are needed.

# Process and copy .desktop file
echo "-> Configurando acceso directo (.desktop)..."
# We need to modify the Exec and Icon paths for the installed location
cp "$DESKTOP_FILE" "$BUILD_DIR/usr/share/applications/"
sed -i "s|Exec=.*|Exec=$INSTALL_DIR/$APP_NAME|" "$BUILD_DIR/usr/share/applications/$DESKTOP_FILE"
sed -i "s|Icon=.*|Icon=$APP_NAME|" "$BUILD_DIR/usr/share/applications/$DESKTOP_FILE"

# Install icon
echo "-> Instalando icono..."
if [ -f "$ICON_FILE" ]; then
    cp "$ICON_FILE" "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
else
    echo "Advertencia: Icono no encontrado en $ICON_FILE"
fi

# Copy postinst and prerm scripts
echo "-> Añadiendo scripts de instalación..."
if [ -f "debian/postinst" ]; then
    cp "debian/postinst" "$BUILD_DIR/DEBIAN/"
    chmod 755 "$BUILD_DIR/DEBIAN/postinst"
fi

if [ -f "debian/prerm" ]; then
    cp "debian/prerm" "$BUILD_DIR/DEBIAN/"
    chmod 755 "$BUILD_DIR/DEBIAN/prerm"
fi

# Set permissions
chmod -R 755 "$BUILD_DIR$INSTALL_DIR"

# Build the .deb
echo "-> Construyendo paquete .deb..."
dpkg-deb --build "$BUILD_DIR" "${DEB_NAME}.deb"

echo "=== ¡Éxito! Paquete creado: ${DEB_NAME}.deb ==="
echo "Para instalarlo ejecuta: sudo dpkg -i ${DEB_NAME}.deb"
