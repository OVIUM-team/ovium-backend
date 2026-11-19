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

## Autenticación

- `POST /auth/login` recibe JSON con `username` y `password`. Devuelve
  `access_token` y `token_type` cuando las credenciales son válidas, o HTTP 401
  cuando son incorrectas.
- `GET /auth/session` recibe `Authorization: Bearer <token>`. Devuelve
  `sub`, `role` y `ranch_ids`, o HTTP 401 si el token falta, es inválido o expiró.
  El JWT vence en 30 minutos.
- Configura `JWT_SECRET` con un valor aleatorio de al menos 32 bytes. Para
  PostgreSQL, usa una URL SQLAlchemy con el prefijo `postgresql+psycopg://`.
- El acceso a cuentas está aislado en `app/models/auth.py`. Mientras se integra
  con las migraciones del núcleo, el modelo de referencia usa `auth_accounts`
  y `auth_account_ranches`. El servidor no crea tablas ni datos al arrancar.
  La migración y los datos semilla del equipo deben proveer o adaptar ese
  esquema y guardar únicamente hashes Argon2 generados con
  `app.services.auth.password_hasher.hash`.

### Permisos por rancho

Para una ruta bajo `/ranchos/{ranch_id}`, usa
`Depends(require_ranch_access(RanchPermission.READ))` (o `CAPTURE`, `EDIT`,
`EXPORT` según la operación). En cada petición se consulta el rol y la
membresía vigentes en la base. Filtra también las lecturas y escrituras del
recurso por el mismo `ranch_id`; las rutas no deben aceptar un rancho
diferente en el cuerpo de la petición.

El modelo de referencia guarda las cuatro autorizaciones de cada rama en
`auth_account_ranches`, apagadas por defecto. Para técnicos y asociaciones,
el modelo requiere una membresía por cada rancho afiliado. La integración
con las migraciones debe conectar ese acceso con las afiliaciones vigentes.
