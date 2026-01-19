# Repositorio APT de Cogny

## Instalación

```bash
# 1. Añadir clave
curl -fsSL https://Maalfer.github.io/cogny/cogny.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/cogny-archive-keyring.gpg

# 2. Añadir repo
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cogny-archive-keyring.gpg] https://Maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/cogny.list > /dev/null

# 3. Instalar
sudo apt update
sudo apt install cogny
```
