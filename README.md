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

```powershell
docker compose up --build -d --wait
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

SQL Server Express conserva sus datos en el volumen `sqlserver-data`. La API
espera a que SQL Server responda a una consulta antes de iniciar. La versión
actual de FastAPI ofrece `/health`, que verifica el proceso HTTP. Cuando se
integre la persistencia, el servidor SQL estará disponible como `db:1433`
desde el contenedor de la API.

Para ejecutar una consulta de verificación en SQL Server:

```sh
docker compose exec db sh -c '/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -b -Q "SELECT 1"'
```

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
