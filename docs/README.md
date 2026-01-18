# Repositorio APT de Cogny

## Instalación rápida
```bash
curl -fsSL https://maalfer.github.io/cogny/cogny.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/cogny-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cogny-archive-keyring.gpg] https://maalfer.github.io/cogny stable main" | sudo tee /etc/apt/sources.list.d/cogny.list
sudo apt update
sudo apt install cogny
```
