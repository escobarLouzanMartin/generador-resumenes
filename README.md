# Generador de Resúmenes de Subasta

Aplicación web para llevar el control de subastas: cargar compras (comprador, carta y precio), generar resúmenes agrupados por comprador y mantener un historial de subastas cerradas con estadísticas.

## Funcionalidad

### Cuentas
- Registro e inicio de sesión con usuario y contraseña (contraseñas hasheadas, nunca en texto plano).
- Cada usuario ve únicamente sus propias subastas.

### Subasta actual
- Carga de compras: comprador, contacto (opcional), carta y precio.
- **Autocompletado de comprador**: al escribir un nombre ya usado en *cualquier* subasta anterior (no solo la actual), se sugiere el resto del texto atenuado dentro del mismo campo (estilo Gmail) y se completa presionando `Tab`. Si ese comprador ya tiene un contacto cargado, se autocompleta también.
- Edición y eliminación de compras individuales.
- Resúmenes automáticos agrupados por comprador, con el total de cada uno y el total general.
- **Copiar resumen**: cada resumen tiene un botón que copia al portapapeles solo el listado de cartas con sus precios y el total, listo para pegar y mandarle al comprador (sin nombre ni contacto).
- **Cerrar subasta**: archiva la subasta actual (queda disponible en el historial y suma a las estadísticas) y abre una nueva automáticamente.

### Historial
- Listado de todas las subastas cerradas, con fecha, cantidad de compradores y total.
- Detalle de cada subasta pasada con sus resúmenes completos, en modo solo lectura.

### Estadísticas
- Total generado entre todas las subastas cerradas.
- Cantidad de subastas cerradas y promedio generado por subasta.
- Compradores más fieles (por cantidad de subastas distintas en las que compraron).
- Compradores que más gastaron en total.
- Gráfico de evolución del total generado por subasta.

## Stack

- **Backend**: Python + [Flask](https://flask.palletsprojects.com/)
- **Base de datos**: PostgreSQL vía [SQLAlchemy](https://www.sqlalchemy.org/) (en local, si no hay `DATABASE_URL` configurada, cae automáticamente a SQLite para poder probar sin instalar Postgres)
- **Autenticación**: [Flask-Login](https://flask-login.readthedocs.io/) + hashing de contraseñas con Werkzeug
- **Frontend**: HTML, CSS y JavaScript vanilla (sin frameworks ni build step), gráficos con [Chart.js](https://www.chartjs.org/) vía CDN
- **Servidor de producción**: [Gunicorn](https://gunicorn.org/)

## Cómo correrlo localmente

```bash
# 1. Clonar el repo
git clone https://github.com/escobarLouzanMartin/generador-resumenes.git
cd generador-resumenes

# 2. Crear un entorno virtual (opcional pero recomendado)
python3 -m venv venv
source venv/bin/activate   # en Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Correr la app
python app.py
```

La app queda disponible en `http://localhost:5000`. Sin configurar nada más, usa un archivo SQLite local (`instance/local.db`) que se crea solo. Para probar contra Postgres en local, seteá la variable de entorno `DATABASE_URL` antes de correr la app:

```bash
export DATABASE_URL="postgresql://usuario:password@localhost:5432/generador_resumenes"
python app.py
```

## Estructura del proyecto

```
generador-resumenes/
├── app.py                       # Backend Flask: rutas, auth y lógica de subastas
├── models.py                    # Modelos de base de datos (User, Auction, Purchase)
├── static/
│   └── style.css                # Estilos compartidos por todas las páginas
├── templates/
│   ├── _nav.html                 # Barra de navegación superior (reutilizable)
│   ├── login.html
│   ├── registro.html
│   ├── index.html                # Subasta actual
│   ├── historial.html            # Listado de subastas cerradas
│   ├── historial_detalle.html    # Detalle de una subasta pasada
│   └── estadisticas.html         # Estadísticas y gráficos
├── requirements.txt
├── render.yaml                   # Config de despliegue en Render (incluye base Postgres)
└── README.md
```

## Endpoints

| Método | Ruta                    | Descripción                                                       |
|--------|-------------------------|---------------------------------------------------------------------|
| GET/POST | `/registro`           | Crear cuenta                                                      |
| GET/POST | `/login`              | Iniciar sesión                                                    |
| GET    | `/logout`               | Cerrar sesión                                                     |
| GET    | `/`                     | Página principal (subasta actual)                                  |
| GET    | `/compras`              | Compras de la subasta actual (JSON)                                |
| POST   | `/agregar`              | Agrega una compra (`comprador`, `contacto`, `carta`, `precio`)     |
| POST   | `/eliminar`             | Elimina una compra por índice (`index`)                           |
| POST   | `/limpiar`              | Borra todas las compras de la subasta actual                       |
| GET    | `/resumenes`            | Resúmenes agrupados por comprador de la subasta actual (JSON)      |
| POST   | `/cerrar_subasta`       | Cierra la subasta actual y abre una nueva                          |
| GET    | `/compradores`          | Compradores históricos del usuario, para el autocompletado (JSON) |
| GET    | `/historial`            | Listado de subastas cerradas                                       |
| GET    | `/historial/<id>`       | Detalle de una subasta cerrada                                     |
| GET    | `/estadisticas`         | Página de estadísticas                                             |
| GET    | `/api/estadisticas`     | Datos agregados para las estadísticas y el gráfico (JSON)           |

## Despliegue en Render

El `render.yaml` incluye tanto el servicio web como una base de datos Postgres gratuita, conectadas automáticamente mediante la variable `DATABASE_URL`. Al desplegar desde Render con "Blueprint" (usando este `render.yaml`), no hace falta configurar nada más: Render crea la base, genera un `SECRET_KEY` aleatorio y arranca la app con Gunicorn.

## Notas

- Las contraseñas se guardan hasheadas (nunca en texto plano).
- Cada usuario solo puede ver y modificar sus propias subastas.
- Una subasta permanece "abierta" hasta que se cierra explícitamente con el botón correspondiente; mientras está abierta se le pueden seguir agregando, editando o eliminando compras.
