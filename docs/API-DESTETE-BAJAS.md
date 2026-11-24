# API de destete y bajas

Las rutas parten de `/ranchos/{ranch_id}/animales/{animal_id}` y requieren
`Authorization: Bearer <token>`. Pueden consultarse y probarse en `/docs`.

| Método y ruta | Permiso | Resultado |
|---|---|---|
| POST /destete | captura | Registra un único destete por animal |
| GET /destete | lectura | Consulta el destete |
| POST /baja | edición | Registra la baja y cambia el animal a `baja` en una transacción |
| GET /baja | lectura | Consulta la baja conservada |

Destete: `{"fecha":"2026-03-17","destino":"recria","pesaje_id":null}`.
Destinos admitidos: `engorda`, `venta`, `recria`. El pesaje es opcional;
si se envía, debe existir, pertenecer al mismo animal, ser de tipo `destete`
y coincidir con la fecha del evento. Se registra primero mediante la API de pesajes.
El destino `venta` no registra automáticamente una baja.

Baja: `{"fecha":"2026-04-01","motivo":"Venta"}`. El motivo es obligatorio
y no puede contener solamente espacios. Ambos POST admiten `id` UUID opcional
generado por el cliente; si se omite, el servidor lo genera. La identidad de
quien registra se toma exclusivamente de la sesión autenticada.

No se aceptan fechas futuras ni anteriores al nacimiento conocido. No se
destetan animales dados de baja. Un UUID repetido, un segundo destete o una
segunda baja devuelve 409; no constituye una confirmación de sincronización.
La consulta de un evento aún no registrado devuelve 404. Los permisos y
el rancho se verifican en cada petición. No se eliminan animales ni su historial.

Validación: `python -m unittest discover -s tests -v`.
Las pruebas usan una base SQLite temporal creada mediante Alembic y verifican
fechas, referencias, duplicados, acceso y rollback de una baja fallida.
