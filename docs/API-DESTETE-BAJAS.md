# API de destete y bajas

Tarjeta: https://trello.com/c/5ubT3n3w/34-api-de-destete-y-bajas

Las rutas parten de `/ranchos/{ranch_id}/animales/{animal_id}` y requieren
`Authorization: Bearer <token>`. Pueden consultarse y probarse en `/docs`.

| Método y ruta | Permiso | Resultado |
|---|---|---|
| POST /destete | captura | Registra un único destete por animal |
| GET /destete | lectura | Consulta el destete |
| POST /baja | edición | Registra la baja y cambia el animal a `baja` en una transacción |
| GET /baja | lectura | Consulta la baja conservada |

Destete: `{"fecha":"2026-03-17","destino":"recria","peso":25.50}`.
Destinos admitidos: `engorda`, `venta`, `recria`. Se debe proporcionar exactamente
uno de `peso` (crea un pesaje de destete en la misma transacción) o `pesaje_id`.
Si se envía `pesaje_id`, debe existir, pertenecer al mismo animal, ser de tipo
`destete` y coincidir con la fecha del evento. Se registra primero mediante la API de pesajes.
El destino `venta` no registra automáticamente una baja.

Baja: `{"fecha":"2026-04-01","motivo":"venta"}`. Los motivos admitidos son
`muerte`, `venta` y `desecho`, normalizados a minúsculas. Ambos POST admiten `id` UUID opcional
generado por el cliente; si se omite, el servidor lo genera. La identidad de
quien registra se toma exclusivamente de la sesión autenticada.

No se aceptan fechas futuras ni anteriores al nacimiento conocido. No se
destetan animales dados de baja. Un UUID repetido, un segundo destete o una
segunda baja devuelve 409; no constituye una confirmación de sincronización.
La consulta de un evento aún no registrado devuelve 404. Los permisos y
el rancho se verifican en cada petición. No se eliminan animales ni su historial.

La madre pasa de `lactancia` a `mantenimiento` cuando ya no quedan crías vivas
y activas pendientes de destete en su parto más reciente. En partos múltiples,
confirmar solo una cría no termina la lactancia de sus hermanas. Un destete de
un parto anterior no cambia una lactancia posterior. Si no hay registros de
parto, se usa la relación madre–cría del inventario. La actualización de la
madre, el pesaje y el destete comparten transacción.

El inventario vivo se consulta con `GET /ranchos/{ranch_id}/animales?estado=activo`.
La baja deja de aparecer allí, pero conserva su ficha e historial.
`GET /ranchos/{ranch_id}/bajas` permite filtros `motivo`, `desde` y `hasta`;
`motivo=muerte` permite obtener el número de muertes por periodo para calcular
mortalidad con el denominador de población que defina el reporte. Esta API no
inventa un porcentaje sin ese denominador. Los datos históricos con motivos
libres no se reclasifican automáticamente.

Validación: `python -m unittest discover -s tests -v`.
Las pruebas usan una base SQLite temporal creada mediante Alembic y verifican
fechas, referencias, duplicados, acceso y rollback de una baja fallida.
