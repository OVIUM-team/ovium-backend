# API de OVIUM

Desde la raíz del proyecto, con Python 3.10 o superior:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
```

En otra terminal:

```sh
curl -fsS http://127.0.0.1:8000/health
```

La respuesta esperada es HTTP 200 con `{"status":"ok"}`.
`/health` comprueba que la aplicación responde y funciona sin una base de datos.

La configuración lee `DATABASE_URL` y `JWT_SECRET` del entorno o de
`.env`. Las variables del entorno tienen prioridad. Completa esos valores
cuando integres la base de datos y la autenticación. Guarda los valores
locales en `.env`, que Git ignora.

`app/routes` contiene los endpoints. Usa `app/models` para los modelos de
persistencia y `app/schemas` para los esquemas de entrada y salida.
Para Docker Compose, el punto de entrada es `app.main:app`. Inicia Uvicorn
con `--host 0.0.0.0` dentro del contenedor.

## Portal web

Configura `CORS_ORIGINS` como lista JSON de orígenes exactos del portal. Para
Vite en local, `.env.example` ya incluye `CORS_ORIGINS=["http://localhost:5173"]`.
Copia ese valor a `.env` si ya tienes uno y reinicia la API. En despliegue, usa el origen HTTPS del portal, sin ruta ni barra final.
Si la lista está vacía, las peticiones desde otros orígenes quedan bloqueadas
por el navegador.

## Autenticación y datos

- `POST /auth/login` recibe `username` (el correo de la cuenta) y `password`.
  Devuelve un JWT de 30 minutos con el rol y los ranchos.
- `GET /auth/session` valida `Authorization: Bearer <token>`.
- Configura `JWT_SECRET` con un valor aleatorio de al menos 32 bytes. Para
  SQL Server, usa el dialecto `mssql+pyodbc` con Microsoft ODBC Driver 18.
  El servidor requiere el esquema creado por las migraciones del equipo.
- Las tablas declaradas en `app/models` mapean las columnas del diagrama ER.
  La API no crea tablas al arrancar. Las migraciones deben garantizar un
  rancho por propietario, correos únicos e identificadores oficiales únicos.

## Ranchos y animales

- `GET /ranchos` lista los ranchos visibles. El productor puede crear su rancho
  con `POST /ranchos` y registrar subcuentas con `POST /ranchos/{id}/ramas`.
  Las cuatro autorizaciones de cada rama empiezan deshabilitadas por defecto.
- Los endpoints de animales están bajo `/ranchos/{id}/animales`. El listado
  filtra por `sexo`, `raza_id` y `estado`. `PUT` reemplaza los datos y la lista
  de identificadores en una transacción. `POST /{animal_id}/baja` registra
  fecha y motivo y conserva el animal.
- Una madre o un padre desconocido se representa con `null`. Un progenitor
  externo conocido se registra en el mismo inventario con sus datos de
  criador o propietario. La API no cruza datos entre ranchos.
- La arquitectura contempla una sola asociación que puede leer todos los
  ranchos. Un técnico lee sus ranchos afiliados. Para una rama, la API
  verifica la membresía y el permiso correspondiente en cada petición.

Para correr las pruebas de integración con una base SQLite temporal:

```sh
python -m pip install httpx httpx2
python -m unittest discover -s tests -v
```

## Entorno local con Docker Compose

En Windows, abre Docker Desktop en modo de contenedores Linux. Desde PowerShell
en la carpeta `ovium-backend`, copia la configuración si todavía no tienes
un archivo `.env`:

```powershell
Copy-Item .env.example .env
```

Edita `.env` y asigna a `MSSQL_SA_PASSWORD` una contraseña local de al menos
8 caracteres que combine mayúsculas, minúsculas, números y símbolos. Puedes
ponerla entre comillas simples para evitar que Compose interprete símbolos
como `$`. Si ya tienes `.env`, agrega esta variable a tu archivo.

Para verificar la conexión desde la API, copia el ejemplo comentado de
`DATABASE_URL` de `.env.example` a `.env`. Quita el `#` y cambia
`TU_CLAVE_CODIFICADA` por la contraseña de `sa` codificada para URL.
En PowerShell puedes obtenerla con `[uri]::EscapeDataString('tu contraseña local')`.
El ejemplo usa `master` para la prueba inicial. Para usar las rutas de la API,
configura la base de Ovium con las migraciones aplicadas y define `JWT_SECRET`.

```powershell
docker compose up --build -d --wait
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

SQL Server Express conserva sus datos en el volumen `sqlserver-data`. Desde
Windows, las herramientas de SQL Server y Alembic pueden conectarse a
`127.0.0.1,1433`. Desde la API en Docker, el servidor es `db:1433`.

`/health` verifica que la API responda por HTTP. Para verificar también el
driver y la conexión a SQL Server usando `DATABASE_URL`, ejecuta lo siguiente
desde PowerShell en el backend:

```powershell
docker compose exec -T api python -c "from app.config import Settings; from sqlalchemy import create_engine, text; url = Settings().database_url; assert url, 'Define DATABASE_URL en .env'; engine = create_engine(url, connect_args=dict(timeout=5)); conn = engine.connect(); result = conn.execute(text('SELECT 1')).scalar_one(); conn.close(); engine.dispose(); print(result)"
```

La consulta debe imprimir `1`.

Para levantar también el portal, coloca ambos repositorios en la misma carpeta,
con los nombres `ovium-backend` y `ovium-web`. En el repo web usa
`feature/proyecto-web-base` o una rama que ya incluya ese proyecto, y conserva
`http://localhost:5173` en `CORS_ORIGINS` del backend. Desde `ovium-backend`:

```sh
docker compose --profile web up --build -d --wait
```

Abre http://localhost:5173. Para ver los registros usa `docker compose logs`.
Para detener los servicios conservando los datos usa
`docker compose --profile web down`.
