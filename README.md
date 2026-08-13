# Generador de Resúmenes de Subasta

Aplicación web simple para cargar las compras de una subasta (comprador, carta y precio) y generar automáticamente un resumen agrupado por comprador, listo para copiar y enviar.

## Funcionalidad

- **Carga de compras**: comprador, contacto (opcional), carta y precio.
- **Autocompletado de comprador**: al escribir un nombre ya cargado, se sugiere el resto del texto atenuado dentro del mismo campo (estilo Gmail) y se completa presionando `Tab`. Si el comprador ya tiene un contacto cargado, se autocompleta también.
- **Edición y eliminación** de compras individuales.
- **Resúmenes automáticos** agrupados por comprador, con el total de cada uno y el total general.
- **Copiar resumen**: cada resumen tiene un botón que copia al portapapeles solo el listado de cartas con sus precios y el total, listo para pegar y mandarle al comprador (sin nombre ni contacto).
- Los datos de contacto se muestran únicamente en la vista del vendedor (no en el texto copiado).
- Las compras se guardan en la sesión del navegador (no hay base de datos), así que se pierden al limpiar cookies o en otra sesión.

## Stack

- **Backend**: Python + [Flask](https://flask.palletsprojects.com/)
- **Frontend**: HTML, CSS y JavaScript vanilla (todo en `templates/index.html`, sin frameworks ni build step)
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

La app queda disponible en `http://localhost:5000`.

## Estructura del proyecto

```
generador-resumenes/
├── app.py                  # Backend Flask: rutas y lógica de resúmenes
├── templates/
│   └── index.html          # Frontend: UI, estilos y JS
├── requirements.txt        # Dependencias de Python
├── render.yaml              # Config de despliegue en Render
└── README.md
```

## Endpoints

| Método | Ruta         | Descripción                                                    |
|--------|--------------|------------------------------------------------------------------|
| GET    | `/`          | Sirve la página principal                                        |
| GET    | `/compras`   | Devuelve todas las compras cargadas (JSON)                       |
| POST   | `/agregar`   | Agrega una compra (`comprador`, `contacto`, `carta`, `precio`)   |
| POST   | `/eliminar`  | Elimina una compra por índice (`index`)                          |
| POST   | `/limpiar`   | Borra todas las compras cargadas                                 |
| GET    | `/resumenes` | Devuelve los resúmenes agrupados por comprador (JSON)            |

## Despliegue

El repo incluye un `render.yaml` para desplegar directamente en [Render](https://render.com/) como Web Service, usando Gunicorn como servidor.

## Notas

- No hay persistencia en base de datos: las compras viven en la sesión de Flask (cookie del navegador). Si necesitás que los datos persistan entre dispositivos o sesiones, habría que agregar una base de datos.
- No hay autenticación: cualquiera que acceda a la URL puede cargar y ver sus propias compras (aisladas por sesión).
