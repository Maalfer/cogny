#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# ============================================
# Script de Gestión del Repositorio APT
# ============================================
# Este script automáticamente:
# 1. Compila el paquete .deb
# 2. Crea/actualiza el repositorio APT
# 3. Firma los paquetes con GPG
# 4. Prepara los archivos para GitHub Pages

# Configuración
APP_NAME="cogny"
VERSION="1.0.3"
ARCH="amd64"
DEB_FILE="${APP_NAME}_${VERSION}_${ARCH}.deb"
APT_REPO_DIR="docs"  # Usar docs/ directamente para GitHub Pages
GPG_KEY_ID=""  # Dejar vacío para usar la clave por defecto

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Gestor de Repositorio APT para $APP_NAME ===${NC}\n"

# ============================================
# Paso 1: Verificar Dependencias
# ============================================
echo -e "${YELLOW}→ Verificando dependencias...${NC}"

command -v dpkg-deb >/dev/null 2>&1 || { echo -e "${RED}Error: dpkg-deb no está instalado.${NC}"; exit 1; }
command -v gpg >/dev/null 2>&1 || { echo -e "${RED}Error: gpg no está instalado. Ejecuta: sudo apt install gpg${NC}"; exit 1; }

if ! command -v reprepro >/dev/null 2>&1; then
    echo -e "${YELLOW}reprepro no encontrado. Instalándolo...${NC}"
    sudo apt install -y reprepro
fi

# ============================================
# Paso 2: Compilar el .deb si no existe
# ============================================
if [ ! -f "$DEB_FILE" ] || [ "$GITHUB_ACTIONS" = "true" ]; then
    echo -e "${YELLOW}→ Compilando paquete (Forzado en CI/CD o archivo no encontrado)...${NC}"
    if [ -f "scripts/compilar-deb.sh" ]; then
        ./scripts/compilar-deb.sh
    else
        echo -e "${RED}Error: scripts/compilar-deb.sh no encontrado.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Paquete $DEB_FILE encontrado.${NC}"
fi

# ============================================
# Paso 3: Configurar Clave GPG
# ============================================
echo -e "\n${YELLOW}→ Configurando firmado GPG...${NC}"

# Si no se especificó KEY_ID, intentar detectarla o importarla
if [ -z "$GPG_KEY_ID" ]; then
    # Revisar si se pasaron claves por variables de entorno (CI/CD)
    if [ -n "$GPG_PRIVATE_KEY" ]; then
        echo -e "${YELLOW}→ Importando clave privada GPG desde variable de entorno...${NC}"
        # Ensure we handle newlines correctly if passed as a single line or with escaped newlines
        echo "$GPG_PRIVATE_KEY" | sed 's/\\n/\n/g' | tr -d '\r' | gpg --batch --import || {
             echo -e "${RED}Error: Falló la importación de la clave GPG.${NC}"
             exit 1
        }
        
        GPG_KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | grep sec | head -n1 | awk '{print $2}' | cut -d'/' -f2)
    else
        echo -e "${YELLOW}→ Buscando clave GPG disponible en el sistema...${NC}"
        # Intentar obtener solo claves secretas, eliminar cabeceras, tomar la primera
        # Use --with-colons for machine readable output
        # Format: sec:u:2048:1:KEYID:......
        GPG_KEY_ID=$(gpg --list-secret-keys --with-colons | grep '^sec' | head -n1 | cut -d':' -f5)
        
        if [ -z "$GPG_KEY_ID" ]; then
            # Fallback to old parsing if --with-colons fails or behaves oddly
             GPG_KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | grep sec | head -n1 | awk '{print $2}' | cut -d'/' -f2)
        fi
    fi
    
    if [ -z "$GPG_KEY_ID" ]; then
        echo -e "${RED}Error: No se encontró ninguna clave GPG privada en el sistema.${NC}"
        echo -e "${YELLOW}Debes generar una clave GPG antes de continuar:${NC}"
        echo -e "${GREEN}  gpg --full-generate-key${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Clave detectada: $GPG_KEY_ID${NC}"
else
    echo -e "${GREEN}✓ Usando GPG_KEY_ID proporcionada: $GPG_KEY_ID${NC}"
fi

# Exportar clave pública
gpg --armor --export $GPG_KEY_ID > ${APP_NAME}.gpg.key
echo -e "${GREEN}✓ Clave pública exportada a ${APP_NAME}.gpg.key${NC}"

# ============================================
# Paso 4: Crear Estructura del Repositorio
# ============================================
echo -e "\n${YELLOW}→ Configurando estructura del repositorio...${NC}"

mkdir -p ${APT_REPO_DIR}/conf

# Crear archivo de configuración distributions
if [ -n "$GPG_PASSPHRASE" ] && [ -n "$GPG_PRIVATE_KEY" ]; then
    # En CI/CD con passphrase, firmamos manualmente para evitar problemas con gpg-agent
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
    # En local o sin passphrase explícita, dejamos que reprepro firme (usa gpg-agent local)
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

echo -e "${GREEN}✓ Configuración del repositorio creada.${NC}"

# ============================================
# Paso 5: Añadir/Actualizar Paquete
# ============================================
echo -e "\n${YELLOW}→ Añadiendo paquete al repositorio...${NC}"

# Eliminar versión anterior si existe
reprepro -b ${APT_REPO_DIR} remove stable ${APP_NAME} 2>/dev/null || true

# Añadir nueva versión
reprepro -b ${APT_REPO_DIR} includedeb stable ${DEB_FILE}

# Firmado manual si es necesario
if [ "$DO_MANUAL_SIGN" = true ]; then
    echo -e "${YELLOW}→ Firmando manualmente Release e InRelease...${NC}"
    RELEASE_FILE="${APT_REPO_DIR}/dists/stable/Release"
    
    # Release.gpg (detached signature)
    rm -f "${RELEASE_FILE}.gpg"
    echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -u "$GPG_KEY_ID" --detach-sign --armor --output "${RELEASE_FILE}.gpg" "$RELEASE_FILE"
    
    # InRelease (clearsign)
    rm -f "${APT_REPO_DIR}/dists/stable/InRelease"
    echo "$GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 --pinentry-mode loopback -u "$GPG_KEY_ID" --clearsign --output "${APT_REPO_DIR}/dists/stable/InRelease" "$RELEASE_FILE"
    
    echo -e "${GREEN}✓ Firmado manual completado.${NC}"
fi

echo -e "${GREEN}✓ Paquete añadido al repositorio.${NC}"

# ============================================
# Paso 6: Copiar clave pública al repo
# ============================================
cp ${APP_NAME}.gpg.key ${APT_REPO_DIR}/

# ============================================
# Paso 7: Crear archivo README para el repositorio
# ============================================
cat > ${APT_REPO_DIR}/README.md <<EOF
# Repositorio APT de Cogny

## Instalación

Para instalar Cogny desde este repositorio:

\`\`\`bash
# 1. Añadir la clave GPG
curl -fsSL https://Maalfer.github.io/cogny/${APP_NAME}.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/${APP_NAME}-archive-keyring.gpg

# 2. Añadir el repositorio
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/${APP_NAME}-archive-keyring.gpg] https://Maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/${APP_NAME}.list > /dev/null

# 3. Actualizar e instalar
sudo apt update
sudo apt install ${APP_NAME}
\`\`\`

## Actualizar

\`\`\`bash
sudo apt update
sudo apt upgrade ${APP_NAME}
\`\`\`
EOF

# ============================================
# Paso 8: Publicación Automática en GitHub
# ============================================
# Si estamos en GitHub Actions, dejamos que el paso siguiente (git-auto-commit-action) maneje el push
if [ "$GITHUB_ACTIONS" = "true" ]; then
    echo -e "\n${YELLOW}→ Entorno GitHub Actions detectado: Saltando push manual.${NC}"
    echo -e "${YELLOW}Se utilizará git-auto-commit-action para guardar los cambios en 'docs'.${NC}"
else
    echo -e "\n${YELLOW}→ Publicando en GitHub...${NC}"

    # Verificar si git está instalado
    if ! command -v git >/dev/null 2>&1; then
        echo -e "${RED}Error: git no está instalado.${NC}"
        exit 1
    fi

    # Añadir cambios
    echo -e "${YELLOW}→ git add docs${NC}"
    git add docs

    # Commit
    echo -e "${YELLOW}→ git commit${NC}"
    git commit -m "Update APT repository v${VERSION}" || echo "Nada que commitear"

    # Push
    echo -e "${YELLOW}→ git push${NC}"
    if git push origin main; then
        echo -e "${GREEN}✓ Publicado exitosamente en GitHub.${NC}"
    else
        echo -e "${RED}Error al hacer push. Verifica tu configuración de git remote.${NC}"
        # Intentar master si main falla, por si acaso
        # git push origin master
    fi
fi

echo -e "\n${GREEN}=== ¡Proceso Completado! ===${NC}\n"
echo -e "El repositorio debería estar disponible pronto en:"
echo -e "${GREEN}https://Maalfer.github.io/cogny/${NC}"
