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
