# Repositorio APT de Cogny

Repositorio oficial para instalar **Cogny** en distribuciones Linux basadas en Debian.

## 📦 Instalación

Para instalar Cogny desde este repositorio APT:

```bash
# 1. Añadir la clave GPG del repositorio
curl -fsSL https://maalfer.github.io/cogny/cogny.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/cogny-archive-keyring.gpg

# 2. Añadir el repositorio a tus fuentes APT
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cogny-archive-keyring.gpg] https://maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/cogny.list

# 3. Actualizar la lista de paquetes e instalar
sudo apt update
sudo apt install cogny
```

## 🔄 Actualizar Cogny

Para actualizar a la última versión:

```bash
sudo apt update
sudo apt upgrade cogny
```

## 🗑️ Desinstalar

```bash
sudo apt remove cogny
```

---

## 📚 Más Información

- **Repositorio del Código Fuente:** [github.com/Maalfer/cogny](https://github.com/Maalfer/cogny)
- **Documentación:** Consulta el README principal del proyecto
- **Reporte de Bugs:** [Issues en GitHub](https://github.com/Maalfer/cogny/issues)

---

*Este repositorio está alojado en GitHub Pages y es firmado con GPG para garantizar la autenticidad de los paquetes.*
