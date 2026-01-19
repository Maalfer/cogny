# Repositorio APT de Cogny

## Instalación

Para instalar Cogny desde este repositorio:

```bash
# 1. Añadir la clave GPG
curl -fsSL https://Maalfer.github.io/cogny/cogny.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/cogny-archive-keyring.gpg

# 2. Añadir el repositorio
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cogny-archive-keyring.gpg] https://Maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/cogny.list > /dev/null

# 3. Actualizar e instalar
sudo apt update
sudo apt install cogny
```

## Actualizar

```bash
sudo apt update
sudo apt upgrade cogny
```
