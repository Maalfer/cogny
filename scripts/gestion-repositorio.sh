#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# ============================================
# Script de Gestión del Repositorio APT
# ============================================
# Uso:
#   ./scripts/gestion-repositorio.sh [--setup-ci]
#
# Opciones:
#   --setup-ci   Configura automáticamente los Secretos de GitHub (GPG keys) usando 'gh' CLI.
#                Si no se pasa esta opción, se ejecuta el flujo normal de compilación y despliegue.

# Configuración
APP_NAME="cogny"
VERSION="1.0.3"
ARCH="amd64"
DEB_FILE="${APP_NAME}_${VERSION}_${ARCH}.deb"
APT_REPO_DIR="docs"
GPG_KEY_ID=""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================
# Función: Detectar Clave GPG
# ============================================
detect_gpg_key() {
    if [ -n "$GPG_KEY_ID" ]; then return 0; fi

    echo -e "${YELLOW}→ Buscando clave GPG disponible en el sistema...${NC}"
    # Intentar obtener ID de clave
    GPG_KEY_ID=$(gpg --list-secret-keys --with-colons | grep '^sec' | head -n1 | cut -d':' -f5)
    
    if [ -z "$GPG_KEY_ID" ]; then
        GPG_KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | grep sec | head -n1 | awk '{print $2}' | cut -d'/' -f2)
    fi

    if [ -z "$GPG_KEY_ID" ]; then
        echo -e "${RED}Error: No se encontró ninguna clave GPG privada.${NC}"
        echo -e "${YELLOW}Genera una con: gpg --full-generate-key${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Clave detectada: $GPG_KEY_ID${NC}"
}

# ============================================
# Modo: Setup CI (Configurar GitHub Actions)
# ============================================
setup_ci_secrets() {
    echo -e "${GREEN}=== Configuración Automática de CI/CD (GitHub Actions) ===${NC}\n"

    # 1. Verificar 'gh' CLI
    if ! command -v gh >/dev/null 2>&1; then
        echo -e "${RED}Error: GitHub CLI ('gh') no está instalado.${NC}"
        echo -e "Instálalo con: ${YELLOW}sudo apt install gh${NC}"
        echo -e "Y autentícate con: ${YELLOW}gh auth login${NC}"
        exit 1
    fi

    if ! gh auth status >/dev/null 2>&1; then
        echo -e "${RED}Error: No estás autenticado en GitHub CLI.${NC}"
        echo -e "Ejecuta: ${YELLOW}gh auth login${NC}"
        exit 1
    fi

    # 2. Detectar clave
    detect_gpg_key || exit 1

    # 3. Exportar y subir GPG_PRIVATE_KEY
    echo -e "\n${YELLOW}→ Exportando y subiendo GPG_PRIVATE_KEY a GitHub Secrets...${NC}"
    
    # Exportar a variable (seguro, sin archivo temporal en disco si es posible, 
    # pero gpg suele requerir manejo cuidadoso de binarios/ascii).
    # Usamos --armor para ASCII.
    GPG_DATA=$(gpg --export-secret-keys --armor "$GPG_KEY_ID")
    
    if [ -z "$GPG_DATA" ]; then
        echo -e "${RED}Error al exportar la clave.${NC}"
        exit 1
    fi

    echo "$GPG_DATA" | gh secret set GPG_PRIVATE_KEY --body -
    echo -e "${GREEN}✓ Secreto GPG_PRIVATE_KEY actualizado.${NC}"

    # 4. Configurar GPG_PASSPHRASE
    echo -e "\n${YELLOW}→ Configurando GPG_PASSPHRASE...${NC}"
    echo -e "Introduce la contraseña de tu clave GPG para guardarla como secreto (se ocultará):"
    read -s -p "Passphrase: " USER_PASSPHRASE
    echo ""

    if [ -n "$USER_PASSPHRASE" ]; then
        echo "$USER_PASSPHRASE" | gh secret set GPG_PASSPHRASE --body -
        echo -e "${GREEN}✓ Secreto GPG_PASSPHRASE actualizado.${NC}"
    else
        echo -e "${YELLOW}Nota: No se introdujo contraseña. Si la clave tiene passphase, el CI fallará.${NC}"
    fi

    echo -e "\n${GREEN}=== ¡Configuración de CI Completada! ===${NC}"
    echo -e "Ahora puedes hacer push y GitHub Actions debería poder firmar los paquetes."
    exit 0
}

# Verificar argumentos
if [ "$1" == "--setup-ci" ]; then
    setup_ci_secrets
fi

# ============================================
# Flujo Normal: Compilación y Repositorio
# ============================================

echo -e "${GREEN}=== Gestor de Repositorio APT para $APP_NAME ===${NC}\n"

# Paso 1: Dependencias
echo -e "${YELLOW}→ Verificando dependencias...${NC}"
command -v dpkg-deb >/dev/null 2>&1 || { echo -e "${RED}Error: dpkg-deb falta.${NC}"; exit 1; }
command -v gpg >/dev/null 2>&1 || { echo -e "${RED}Error: gpg falta.${NC}"; exit 1; }

if ! command -v reprepro >/dev/null 2>&1; then
    echo -e "${YELLOW}reprepro no encontrado. Instalándolo...${NC}"
    sudo apt install -y reprepro
fi

# PySide6/Qt Dependencies (Linux)
REQUIRED_LIBS="libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0"
echo -e "${YELLOW}→ Verificando librerías de sistema para PySide6/Qt...${NC}"

# Check for existence of libraries, install if missing
NEEDS_INSTALL=""
for lib in $REQUIRED_LIBS; do
    if ! dpkg -s "$lib" >/dev/null 2>&1; then
        NEEDS_INSTALL="$NEEDS_INSTALL $lib"
    fi
done

if [ -n "$NEEDS_INSTALL" ]; then
    echo -e "${YELLOW}Instalando librerías faltantes:$NEEDS_INSTALL${NC}"
    sudo apt-get update && sudo apt-get install -y $NEEDS_INSTALL
else
    echo -e "${GREEN}✓ Todas las librerías necesarias están instaladas.${NC}"
fi

# Paso 2: Compilar
if [ ! -f "$DEB_FILE" ] || [ "$GITHUB_ACTIONS" = "true" ]; then
    echo -e "${YELLOW}→ Compilando paquete...${NC}"
    if [ -f "scripts/compilar-deb.sh" ]; then
        ./scripts/compilar-deb.sh
    else
        echo -e "${RED}Error: scripts/compilar-deb.sh no encontrado.${NC}"; exit 1
    fi
else
    echo -e "${GREEN}✓ Paquete $DEB_FILE encontrado.${NC}"
fi

# Paso 3: Configurar GPG
echo -e "\n${YELLOW}→ Configurando firmado GPG...${NC}"
if [ -z "$GPG_KEY_ID" ]; then
    if [ "$GITHUB_ACTIONS" = "true" ] && [ -z "$GPG_PRIVATE_KEY" ]; then
        echo -e "${RED}Error: GPG_PRIVATE_KEY secret is missing in GitHub Actions!${NC}"
        echo -e "Please add it in Settings > Secrets and variables > Actions."
        exit 1
    fi
    if [ -n "$GPG_PRIVATE_KEY" ]; then
        echo -e "${YELLOW}→ Importando clave desde ENV (CI/CD)...${NC}"
        echo "$GPG_PRIVATE_KEY" | sed 's/\\n/\n/g' | tr -d '\r' | gpg --batch --import || {
             echo -e "${RED}Error importando clave.${NC}"; exit 1
        }
        GPG_KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | grep sec | head -n1 | awk '{print $2}' | cut -d'/' -f2)
    else
        detect_gpg_key || exit 1
    fi
    echo -e "${GREEN}✓ Usando ID: $GPG_KEY_ID${NC}"
fi

# Exportar pública
gpg --armor --export $GPG_KEY_ID > ${APP_NAME}.gpg.key
echo -e "${GREEN}✓ Clave pública exportada a ${APP_NAME}.gpg.key${NC}"

# Paso 4: Estructura Repositorio
echo -e "\n${YELLOW}→ Configurando estructura...${NC}"
mkdir -p ${APT_REPO_DIR}/conf

if [ -n "$GPG_PASSPHRASE" ]; then
    # CI/CD: Firma manual
    cat > ${APT_REPO_DIR}/conf/distributions <<EOF
Origin: Cogny
Label: Cogny App
Codename: stable
Architectures: amd64
Components: main
Description: Repositorio Oficial de Cogny
EOF
    DO_MANUAL_SIGN=true
else
    # Local: Firma automática reprepro
    cat > ${APT_REPO_DIR}/conf/distributions <<EOF
Origin: Cogny
Label: Cogny App
Codename: stable
Architectures: amd64
Components: main
Description: Repositorio Oficial de Cogny
SignWith: ${GPG_KEY_ID}
EOF
    DO_MANUAL_SIGN=false
fi

# Paso 5: Actualizar Paquete
echo -e "\n${YELLOW}→ Actualizando repositorio...${NC}"
reprepro -b ${APT_REPO_DIR} remove stable ${APP_NAME} 2>/dev/null || true
reprepro -b ${APT_REPO_DIR} includedeb stable ${DEB_FILE}

if [ "$DO_MANUAL_SIGN" = true ]; then
    echo -e "${YELLOW}→ Firmando manualmente Release e InRelease...${NC}"
    RELEASE_FILE="${APT_REPO_DIR}/dists/stable/Release"
    rm -f "${RELEASE_FILE}.gpg" "${APT_REPO_DIR}/dists/stable/InRelease"
    
    echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -u "$GPG_KEY_ID" --detach-sign --armor --output "${RELEASE_FILE}.gpg" "$RELEASE_FILE"
    echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -u "$GPG_KEY_ID" --clearsign --output "${APT_REPO_DIR}/dists/stable/InRelease" "$RELEASE_FILE"
    echo -e "${GREEN}✓ Firmado manual completado.${NC}"
fi

# Paso 6: Copiar key y README
cp ${APP_NAME}.gpg.key ${APT_REPO_DIR}/
cat > ${APT_REPO_DIR}/README.md <<EOF
# Repositorio APT de Cogny

## Instalación

\`\`\`bash
# 1. Añadir clave
curl -fsSL https://Maalfer.github.io/cogny/${APP_NAME}.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/${APP_NAME}-archive-keyring.gpg

# 2. Añadir repo
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/${APP_NAME}-archive-keyring.gpg] https://Maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/${APP_NAME}.list > /dev/null

# 3. Instalar
sudo apt update
sudo apt install ${APP_NAME}
\`\`\`
EOF

# Paso 7: Publicar
if [ "$GITHUB_ACTIONS" = "true" ]; then
    echo -e "\n${YELLOW}→ CI/CD: Git Auto Commit se encargará del push.${NC}"
else
    echo -e "\n${YELLOW}→ Publicando en GitHub...${NC}"
    if ! command -v git >/dev/null 2>&1; then echo -e "${RED}No hay git.${NC}"; exit 1; fi
    
    git add docs
    git commit -m "Update APT repository v${VERSION}" || echo "Nada que commitear"
    if git push origin main; then
        echo -e "${GREEN}✓ Publicado.${NC}"
    else
        echo -e "${RED}Error en push.${NC}"
    fi
fi

echo -e "\n${GREEN}=== ¡Proceso Completado! ===${NC}\nRepositorio: https://Maalfer.github.io/cogny/"
