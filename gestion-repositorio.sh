#!/bin/bash
set -e

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
VERSION="1.0.1"
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
if [ ! -f "$DEB_FILE" ]; then
    echo -e "${YELLOW}→ El paquete $DEB_FILE no existe. Compilando...${NC}"
    if [ -f "compilar-deb.sh" ]; then
        ./compilar-deb.sh
    else
        echo -e "${RED}Error: compilar-deb.sh no encontrado.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Paquete $DEB_FILE encontrado.${NC}"
fi

# ============================================
# Paso 3: Configurar Clave GPG
# ============================================
echo -e "\n${YELLOW}→ Configurando firmado GPG...${NC}"

# Si no se especificó KEY_ID, usar la primera clave disponible
if [ -z "$GPG_KEY_ID" ]; then
    GPG_KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | grep sec | head -n1 | awk '{print $2}' | cut -d'/' -f2)
    
    if [ -z "$GPG_KEY_ID" ]; then
        echo -e "${RED}Error: No se encontró ninguna clave GPG.${NC}"
        echo -e "${YELLOW}Genera una con: gpg --full-generate-key${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Usando clave GPG: $GPG_KEY_ID${NC}"
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
cat > ${APT_REPO_DIR}/conf/distributions <<EOF
Origin: Cogny
Label: Cogny App
Codename: stable
Architectures: amd64
Components: main
Description: Repositorio Oficial de Cogny
SignWith: ${GPG_KEY_ID}
EOF

echo -e "${GREEN}✓ Configuración del repositorio creada.${NC}"

# ============================================
# Paso 5: Añadir/Actualizar Paquete
# ============================================
echo -e "\n${YELLOW}→ Añadiendo paquete al repositorio...${NC}"

# Eliminar versión anterior si existe
reprepro -b ${APT_REPO_DIR} remove stable ${APP_NAME} 2>/dev/null || true

# Añadir nueva versión
reprepro -b ${APT_REPO_DIR} includedeb stable ${DEB_FILE}

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
curl -fsSL https://TU_USUARIO.github.io/cogny/${APP_NAME}.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/${APP_NAME}-archive-keyring.gpg

# 2. Añadir el repositorio
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/${APP_NAME}-archive-keyring.gpg] https://TU_USUARIO.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/${APP_NAME}.list > /dev/null

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
# Paso 8: Resumen e Instrucciones
# ============================================
echo -e "\n${GREEN}=== ¡Repositorio APT creado exitosamente! ===${NC}\n"
echo -e "${YELLOW}Siguiente paso: Publicar en GitHub${NC}"
echo -e "
El repositorio ya está en la carpeta ${GREEN}docs/${NC} listo para GitHub Pages.

${YELLOW}Comandos para subir a GitHub:${NC}
   ${GREEN}git add docs
   git commit -m 'Update APT repository v${VERSION}'
   git push${NC}
   
${YELLOW}Luego en GitHub:${NC}
   Settings > Pages > Source: 'main' branch, ${GREEN}/docs${NC} folder

${YELLOW}Los usuarios podrán instalar con:${NC}
   ${GREEN}curl -fsSL https://TU_USUARIO.github.io/cogny/${APP_NAME}.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/${APP_NAME}-archive-keyring.gpg
   echo \"deb [arch=amd64 signed-by=/usr/share/keyrings/${APP_NAME}-archive-keyring.gpg] https://TU_USUARIO.github.io/cogny stable main\" | sudo tee /etc/apt/sources.list.d/${APP_NAME}.list
   sudo apt update && sudo apt install ${APP_NAME}${NC}
"

echo -e "${GREEN}Archivos generados:${NC}"
echo -e "  - ${DEB_FILE}"
echo -e "  - ${APT_REPO_DIR}/ (repositorio en docs/ listo para GitHub Pages)"
echo -e "  - ${APP_NAME}.gpg.key (clave pública)\n"
