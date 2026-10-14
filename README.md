# EntrevistasExpress

Sistema de reservas y gestión de entrevistas (candidatos, profesores,
asignación automática, exportaciones y envío de emails) para la EUEF
(Escuela Universitaria de Enfermería y Fisioterapia "San Juan de Dios",
Fundación San Juan de Dios).

Reconstruido en octubre de 2026 a partir de un único `app.py` monolítico
hacia una estructura modular de fábrica de aplicación Flask, sin cambiar
el comportamiento funcional salvo donde se indica explícitamente más
abajo.

## Estructura del proyecto

```
EntrevistasExpress/
├── app/
│   ├── __init__.py        # create_app() — fábrica de la aplicación
│   ├── config.py          # Configuración leída de variables de entorno
│   ├── constants.py       # Constantes compartidas (p. ej. SEDES_DISPONIBLES)
│   ├── extensions.py      # db, mail (sin la app, evita imports circulares)
│   ├── seed.py            # Siembra inicial: usuario admin + 5 Espacios
│   ├── models/            # Modelos SQLAlchemy (uno por fichero)
│   ├── routes/            # 9 módulos, cada uno con register(app)
│   ├── services/          # Lógica de negocio sin depender de Flask
│   ├── utils/             # Decoradores y helpers varios
│   ├── templates/         # Plantillas Jinja (18 ficheros)
│   └── static/            # CSS, JS, imágenes (13 ficheros)
├── sql/
│   ├── esquema.sql            # Foto fija del esquema (referencia)
│   ├── consultas_utiles.sql   # Consultas de administración (SELECT/UPDATE manuales)
│   └── migraciones.sql        # Registro incremental de cambios de esquema
├── scripts/
│   └── limpieza.ps1       # Elimina del repo los ficheros no usados (Windows/PowerShell)
├── tests/                 # Suite pytest (29 tests, contra SQLite en memoria)
├── run.py                 # Punto de entrada único (dev y producción)
├── environment.yml        # Entorno Conda
├── requirements.txt       # Dependencias de producción
├── requirements-dev.txt   # + pytest, para desarrollo
├── .env.example           # Plantilla de variables de entorno
└── .gitignore
```

### Por qué no hay Blueprints

Cada módulo de `app/routes/` expone `register(app)`, que llama a
`@app.route(...)` directamente sobre la instancia de `app`, en vez de usar
`flask.Blueprint`. Es una decisión deliberada: un Blueprint añade
automáticamente su nombre como prefijo a cada endpoint (p. ej.
`admin.admin_usuarios` en vez de `admin_usuarios`), y las 18 plantillas
tienen más de 25 llamadas a `url_for()` con los nombres planos del
`app.py` original. Usar Blueprints habría obligado a tocar todas esas
plantillas a la vez que se reestructuraba el código Python. Esa migración
a Blueprints queda como una fase futura separada, no mezclada con esta
reconstrucción.

## Instalación

### Opción A: Conda

```bash
conda env create -f environment.yml
conda activate entrevistas-express
```

### Opción B: pip + venv

```bash
python -m venv venv
# Windows: venv\Scripts\activate | Linux/Mac: source venv/bin/activate
pip install -r requirements.txt --break-system-packages
```

Para desarrollo (incluye pytest):

```bash
pip install -r requirements-dev.txt --break-system-packages
```

## Configuración

Copia `.env.example` a `.env` en la raíz del proyecto (junto a `run.py`)
y rellena los valores reales:

```
SECRET_KEY=         # Obligatoria. Genera una con:
                    # python -c "import secrets; print(secrets.token_hex(32))"
DB_USER=postgres
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=entrevistas_db

MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
```

`SECRET_KEY` es obligatoria: si falta, la app se niega a arrancar con un
error claro (ver `app/config.py`) en vez de caer de vuelta a un valor
hardcodeado en silencio.

La base de datos PostgreSQL debe existir vacía (`CREATE DATABASE
entrevistas_db;`) antes de arrancar — `db.create_all()` (dentro de
`app/seed.py`) crea las tablas a partir de los modelos la primera vez
que arranca la app. `sql/esquema.sql` es solo documentación/referencia
del esquema resultante, no algo que haya que cargar a mano.

## Arrancar la aplicación

```bash
# Modo desarrollo (servidor de Flask, debug=True, autoreload)
FLASK_ENV=development python run.py        # PowerShell: $env:FLASK_ENV="development"; python run.py

# Modo producción (Waitress) — por defecto si no se define FLASK_ENV
python run.py
```

Al arrancar por primera vez, se crea automáticamente un usuario
administrador (`admin` / `admin123` — cámbialo tras el primer login) y
los 5 Espacios (días de la semana). Ejecuciones posteriores no duplican
estos datos.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Los 29 tests corren contra SQLite en memoria, nunca contra el PostgreSQL
real — rápidos y aislados, a costa de no cubrir nada específico de
PostgreSQL (como `STRING_AGG` en `sql/consultas_utiles.sql`). Esa parte
solo se verifica ejecutando la app en local contra el Postgres nativo.

## Limitaciones y bugs conocidos

Durante la reconstrucción se encontraron y corrigieron 8 bugs heredados
del `app.py` original (ver el historial de cambios de cada fichero para
el detalle de cada uno: `fecha_email` que no se persistía, tres rutas
que daban 500 en vez de 404 ante un id inexistente, una ruta con el tipo
de clave primaria equivocado, otra con un atributo inexistente, y la
plantilla `admin_estadisticas.html`, que no existía y se ha creado).

Limitaciones que **no** son bugs del código y quedan documentadas aquí
para no volver a investigarlas desde cero:

- **El correo de prueba (`/admin/candidatos/test-email`) puede no
  llegar a Gmail**, aunque los correos reales de la app (confirmación de
  entrevista, agenda) sí llegan. Confirmado que no es un problema de
  autenticación SPF/DKIM/DMARC del dominio ni de la vía de envío SMTP
  (los correos reales usan el mismo mecanismo y sí llegan) — es
  probablemente el contenido genérico de esa plantilla de prueba
  concreta, que los filtros de Gmail tratan con más sospecha. No bloquea
  el uso real de la app.
- **El envío de correo requiere salida saliente al puerto 587** hacia
  `smtp.office365.com`. En redes corporativas segmentadas por VLAN (p.
  ej. WiFi vs. Ethernet), es posible que una VLAN tenga ese puerto
  bloqueado y otra no — si el envío de correo falla con un timeout de
  conexión TCP, es la primera cosa a revisar con el equipo de TI, no un
  bug de la app.

Decisiones pendientes, no resueltas todavía:

- Purga de `uploads/*.xlsx` (Excels de candidatos con datos personales)
  del historial de git — ver la nota en `.gitignore`.

## Convención para cambios de esquema

Cuando se modifique un modelo en `app/models/` de forma que cambie una
tabla ya existente en producción (añadir/quitar/renombrar una columna,
cambiar un tipo), añade el `ALTER TABLE` correspondiente a
`sql/migraciones.sql`, en orden cronológico — `db.create_all()` crea
tablas que no existen, pero no modifica las que ya existen.