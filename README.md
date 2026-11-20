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

## Migraciones y datos semilla (Diana)

Instala `requirements.txt` y configura `DATABASE_URL` en `.env` para una base
SQL Server **vacía**. En Windows se puede usar LocalDB con autenticación integrada:

```text
DATABASE_URL=mssql+pyodbc://@localhost/OviumPruebas?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes
```

El ejemplo anterior corresponde a una instancia local normal. Para LocalDB,
`python scripts/create_test_database.py` crea una base nueva con nombre
`OviumPruebas_<id>` y devuelve su URL exacta. Requiere LocalDB instalado y la
instancia `MSSQLLocalDB` iniciada (`sqllocaldb start MSSQLLocalDB`). No borra ni
reutiliza bases existentes. `TrustServerCertificate=yes` es solo para estas
pruebas locales; en despliegue se debe validar el certificado del servidor.

```sh
python -m alembic upgrade head
python -m alembic current
```

Revisiones, en orden:

1. `0001_nucleo`: usuarios, ranchos, membresías, razas, animales e identificadores.
2. `0002_eventos`: catálogos, partos, crías, pesajes, destetes, bajas, sanidad y fotos.
3. `0003_auditoria`: correcciones inmutables y operaciones de sincronización con ID único.
4. `0004_ajuste_modelo`: mediciones de evaluación y lactancia de 60/75/90 días (75 por defecto).

El [modelo ER actualizado](docs/MODELO-ER.md) describe las columnas y relaciones.
No se usa `metadata.create_all` para desplegar. Las revisiones contienen sus
propias definiciones congeladas y no importan los modelos actuales.

**Bases preexistentes:** estas migraciones iniciales no convierten el script
experimental `base_datos.sql` (tablas PascalCase e IDs enteros) ni bases creadas
manualmente. No ejecutes `stamp head` para saltarte esa diferencia. Se requiere
un respaldo, comparación del esquema y un plan de conversión separado. Los
días de lactancia existentes fuera de 60/75/90 provocan un error explícito en
la revisión 0004; no se sustituyen silenciosamente.

### Datos ficticios de desarrollo

Después de migrar, define `DEMO_PASSWORD` en el entorno (mínimo 12 caracteres)
y ejecuta:

```sh
python -m app.seed --demo
```

El script crea catálogos de razas ovinas, partos de simple a quíntuple,
concepción MN/IA/TE, tipos de pesaje y un rancho demo con estas cuentas:

| Rol de sesión | Correo |
|---|---|
| Productor | productor@demo.ovium.test |
| Rama | rama@demo.ovium.test |
| Técnico | tecnico@demo.ovium.test |
| Asociación | asociacion@demo.ovium.test |

Usan la contraseña proporcionada, almacenada con Argon2 mediante el mismo
servicio que usa el login. Nunca se imprime ni se guarda la contraseña en Git.
La rama se representa como `usuario.tipo=productor` y `usuario_rancho.rol=rama`,
según la API existente. Sus permisos demo están habilitados explícitamente.
La carga es transaccional y repetible: no duplica registros, no reinicia claves
existentes y aborta ante datos demo modificados en vez de sobrescribirlos.
Ejecutar solo en desarrollo; no cargar usuarios demo en producción.

### Validación

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Las pruebas migran una SQLite temporal y validan repetibilidad, login de los
cuatro roles, identificadores únicos, integridad de relaciones, conservación
del animal dado de baja, inmutabilidad de correcciones y rechazo de operaciones
duplicadas. También compilan todas las revisiones al dialecto SQL Server.

Para ejecutar la prueba integral en SQL Server, define
`OVIUM_TEST_DATABASE_URL` con la URL de una base **nueva y vacía** y ejecuta
`python -m unittest discover -s tests -p test_database_workflow.py -v`.
La prueba conserva sus datos para inspección y se niega a usar una base con
tablas existentes. El workflow de GitHub ejecuta ambas variantes.

El registro de `sync_operacion` aporta la clave única y los estados; la futura
API de sincronización deberá guardar operación y evento en la misma transacción.
Las APIs nuevas de eventos, corrección y sincronización pertenecen a otras tarjetas.
El futuro registro de partos debe enviar `cierre_edicion` a 30 días de la captura.
El trigger impide cambiar un parto bloqueado, vencido o que ya tiene correcciones.
