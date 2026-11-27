# API de eventos sanitarios

Tarjeta: https://trello.com/c/bUyfDDZM/33-api-de-eventos-sanitarios

Todas las rutas requieren `Authorization: Bearer <token>` y verifican el acceso
al rancho. POST requiere captura; GET requiere lectura. La documentación
interactiva está en `/docs`.

## Registro individual

`POST /ranchos/{ranch_id}/animales/{animal_id}/eventos-sanitarios`

```json
{
  "fecha": "2026-11-20",
  "tipo": "vacunacion",
  "producto": "Producto aplicado",
  "dosis": "Dosis aplicada con su unidad",
  "observaciones": "Observaciones opcionales"
}
```

Tipos: `vacunacion`, `vitaminas`, `selenio`, `desparasitacion`, `tratamiento`.
El responsable es el usuario autenticado y se devuelve como `responsable_id`.
Puede proporcionarse `id` UUID; si se omite, se genera en el servidor.
Producto y dosis son textos obligatorios: la API registra lo aplicado, no calcula dosis.

## Registro por lote

`POST /ranchos/{ranch_id}/eventos-sanitarios/lote` recibe los mismos campos
y `animales: [{"animal_id":"UUID"}, {"animal_id":"UUID"}]`, con entre 1 y 500
animales distintos del mismo rancho. Cada elemento admite su propio `id` UUID
de evento. El lote es una selección explícita de animales; no requiere tabla
de corrales o lotes. Devuelve una lista con un registro por animal (HTTP 201).

Se valida el lote completo y se guarda en una sola transacción. Si un animal
no pertenece al rancho, está dado de baja, tiene fecha de nacimiento posterior
al evento o existe un UUID repetido, no se guarda ningún registro del lote.
Reenviar un UUID existente devuelve 409; esta ruta no implementa la cola de sincronización.

## Cartilla sanitaria

`GET /ranchos/{ranch_id}/animales/{animal_id}/eventos-sanitarios`

Devuelve una lista ordenada de la fecha más antigua a la más reciente, con
UUID como desempate. Admite filtros opcionales `tipo`, `desde` y `hasta`
(fechas inclusivas). La cartilla permanece disponible después de una baja.
Un animal sin eventos devuelve `[]`; un animal inexistente o ajeno devuelve 404.

Se rechazan fechas futuras, anteriores al nacimiento conocido, textos vacíos,
tipos inválidos y campos desconocidos. Los errores de datos devuelven 422;
sin autenticación se devuelve 401 y sin permiso, 403.

## Pruebas

`python -m unittest discover -s tests -v`

Las pruebas crean una base SQLite temporal con Alembic y verifican los cinco
tipos, el historial, filtros, permisos por rol, aislamiento por rancho,
validaciones, lotes y rollback ante UUID duplicados.
