<p align="center">
  <img src="assets/logo.png" width="120" alt="Cogny">
</p>

<h1 align="center">Cogny</h1>
<p align="center">Bóveda de notas en Markdown, autoalojada y minimalista.</p>
<p align="center"><a href="https://maalfer.github.io/cogny/">maalfer.github.io/cogny</a></p>
<p align="center">
  <a href="https://github.com/Maalfer/cogny/releases/tag/v1.0.0"><img src="https://img.shields.io/github/v/tag/Maalfer/cogny?label=versi%C3%B3n&color=06b6d4" alt="Versión"></a>
</p>

<p align="center"><img src="assets/screenshots/demo1.png" width="850" alt="Bóveda de notas"></p>

## Descripción

Cogny es una aplicación web de notas al estilo Obsidian construida con Django. Las notas viven como archivos Markdown en disco, organizadas en carpetas, sin depender de una base de datos para el contenido. Incluye editor con resaltado de código, fórmulas, diagramas, adjuntos y exportación a PDF con fidelidad completa.

## Capturas

<table>
<tr>
<td width="50%"><img src="assets/screenshots/demo2.png" alt="Exportar a PDF"><br><sub>Exportar cualquier nota a PDF, en claro u oscuro.</sub></td>
<td width="50%"><img src="assets/screenshots/demo3.png" alt="Búsqueda"><br><sub>Búsqueda instantánea por nombre y contenido.</sub></td>
</tr>
<tr>
<td colspan="2"><img src="assets/screenshots/demo4.png" alt="Almacenamiento, optimización de imágenes y backups"><br><sub>Estadísticas de la bóveda, optimización de imágenes a WebP y backup en ZIP antes de aplicarla.</sub></td>
</tr>
</table>

## Características

- Notas en Markdown organizadas en carpetas, guardadas como archivos en disco.
- Editor con resaltado de sintaxis, fórmulas (KaTeX), diagramas (Mermaid) y callouts.
- Exportación de notas a PDF, con imágenes y estilos incrustados.
- Búsqueda instantánea por nombre y por contenido.
- Optimización de imágenes a WebP, al subirlas o en bloque para toda la bóveda, con backup ZIP previo opcional.
- Importación y exportación de la bóveda completa en un único ZIP.
- Progressive Web App instalable, con caché de estáticos para uso offline.

## Stack

- **Backend**: Django + gunicorn (WSGI).
- **Datos**: SQLite para cuentas de usuario; las notas y adjuntos son archivos en disco.
- **Frontend**: JavaScript nativo, sin framework ni paso de compilación.
- **Exportación a PDF**: Chromium headless.

## Desarrollo local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completa DJANGO_SECRET_KEY y las rutas de datos
python manage.py migrate
python manage.py runserver
```

### Con Docker

```bash
docker compose up --build
```

Levanta Cogny en `http://localhost:8000`. Las notas, avatares y la base de datos
se persisten en `./data`. Para crear el primer usuario:

```bash
docker compose exec web python manage.py createsuperuser
```

## Despliegue

`scripts/cogny.service` es la referencia de la unidad systemd usada en producción (gunicorn detrás de un proxy inverso con TLS). Tras cualquier cambio en los estáticos, ejecuta `collectstatic`, sube `ASSET_VERSION` en `.env` y reinicia el servicio para invalidar la caché.
