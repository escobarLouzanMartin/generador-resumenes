# Generador de Resúmenes de Subasta

Aplicación web para gestionar subastas de cartas y otros artículos. Permite cargar compras en tiempo real, generar resúmenes por comprador y llevar un historial completo de subastas.

## Funcionalidades

- **Subasta actual**: cargá compras con comprador, contacto, carta y precio. Los resúmenes se generan automáticamente y podés copiarlos para mandarlos por WhatsApp.
- **Historial**: todas tus subastas cerradas, con posibilidad de editarlas o borrarlas.
- **Compradores**: registro de todos los compradores con su historial de compras y total gastado. Editá nombre y contacto desde acá.
- **Estadísticas**: totales, promedios y ranking de compradores más frecuentes y que más gastaron.
- **Multiusuario**: cada usuario tiene su propia cuenta y sus datos son independientes.

## Tecnologías

- Python + Flask
- SQLAlchemy (SQLite local / PostgreSQL en producción)
- Flask-Login para autenticación
- HTML, CSS y JavaScript vanilla — sin frameworks

## Instalación local

```bash
pip install -r requirements.txt
python app.py
```

Abrí el navegador en `http://localhost:5000`.

## Deploy

Configurado para Render. Requiere las siguientes variables de entorno:

- `SECRET_KEY`: clave secreta para sesiones (generá una con `python -c "import secrets; print(secrets.token_hex(32))"`)
- `DATABASE_URL`: URL de la base de datos PostgreSQL (provista por Render automáticamente)

---

© Martín Escobar Louzán · 2026
