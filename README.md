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
