# Modelo ER de registro de OVIUM

Esquema implementado por las migraciones 0001–0004. Los IDs son UUID del cliente.

```mermaid
erDiagram
  metodo_concepcion {
    uuid id PK
    string codigo
    string nombre
  }
  raza {
    uuid id PK
    string nombre
  }
  tipo_parto {
    uuid id PK
    string nombre
    integer numero_crias
  }
  tipo_pesaje {
    uuid id PK
    string codigo
    string nombre
  }
  usuario {
    uuid id PK
    string nombre
    string email
    string password_hash
    string tipo
  }
  rancho {
    uuid id PK
    string nombre
    string domicilio
    uuid propietario_id FK
    integer dias_lactancia
  }
  animal {
    uuid id PK
    uuid rancho_id FK
    uuid madre_id FK
    uuid padre_id FK
    uuid raza_id FK
    string sexo
    date fecha_nacimiento
    string etapa_vida
    string estado_reproductivo
    string criador
    string propietario
    numeric circunferencia_testicular
    string estado
  }
  sync_operacion {
    uuid id PK
    uuid rancho_id FK
    uuid usuario_id FK
    string estado
    datetime fecha
    string entidad
    uuid registro_id
    string operacion
    string error
  }
  usuario_rancho {
    uuid id PK
    uuid usuario_id FK
    uuid rancho_id FK
    string rol
    boolean puede_leer
    boolean puede_capturar
    boolean puede_editar
    boolean puede_exportar
  }
  animal_identificador {
    uuid id PK
    uuid animal_id FK
    string tipo
    string valor
  }
  baja {
    uuid id PK
    uuid animal_id FK
    date fecha
    string motivo
    uuid registrada_por FK
  }
  evento_sanitario {
    uuid id PK
    uuid animal_id FK
    date fecha
    string tipo
    string producto
    string dosis
    uuid responsable_id FK
    string observaciones
  }
  parto {
    uuid id PK
    uuid madre_id FK
    uuid padre_id FK
    date fecha
    uuid tipo_parto_id FK
    uuid metodo_concepcion_id FK
    uuid registrado_por FK
    datetime fecha_captura
    datetime cierre_edicion
    boolean bloqueado
    string observaciones
  }
  pesaje {
    uuid id PK
    uuid animal_id FK
    date fecha
    uuid tipo_pesaje_id FK
    numeric peso
    numeric circunferencia_testicular
    numeric peso_evaluacion
    uuid registrado_por FK
  }
  correccion {
    uuid id PK
    uuid parto_id FK
    string campo
    string valor_anterior
    string valor_nuevo
    string motivo
    string evidencia
    uuid aprobado_por FK
    datetime fecha
  }
  destete {
    uuid id PK
    uuid animal_id FK
    date fecha
    uuid pesaje_id FK
    string destino
    uuid registrado_por FK
  }
  parto_cria {
    uuid id PK
    uuid parto_id FK
    uuid animal_id FK
    boolean viva
    numeric peso_nacimiento
  }
  foto {
    uuid id PK
    uuid parto_id FK
    string url
    string sha256
    datetime fecha_captura
    uuid registrada_por FK
    uuid correccion_id FK
  }
  usuario ||--o{ rancho : "propietario_id"
  usuario ||--o{ usuario_rancho : "usuario_id"
  rancho ||--o{ usuario_rancho : "rancho_id"
  rancho ||--o{ animal : "rancho_id"
  animal |o--o{ animal : "madre_id"
  animal |o--o{ animal : "padre_id"
  raza |o--o{ animal : "raza_id"
  animal ||--o{ animal_identificador : "animal_id"
  animal ||--o{ baja : "animal_id"
  usuario ||--o{ baja : "registrada_por"
  animal ||--o{ parto : "madre_id"
  animal |o--o{ parto : "padre_id"
  tipo_parto ||--o{ parto : "tipo_parto_id"
  metodo_concepcion ||--o{ parto : "metodo_concepcion_id"
  usuario ||--o{ parto : "registrado_por"
  parto ||--o{ parto_cria : "parto_id"
  animal ||--o{ parto_cria : "animal_id"
  animal ||--o{ pesaje : "animal_id"
  tipo_pesaje ||--o{ pesaje : "tipo_pesaje_id"
  usuario ||--o{ pesaje : "registrado_por"
  animal ||--o{ destete : "animal_id"
  pesaje ||--o{ destete : "animal_id"
  pesaje |o--o{ destete : "pesaje_id"
  usuario ||--o{ destete : "registrado_por"
  animal ||--o{ evento_sanitario : "animal_id"
  usuario ||--o{ evento_sanitario : "responsable_id"
  parto ||--o{ foto : "parto_id"
  usuario ||--o{ foto : "registrada_por"
  correccion |o--o{ foto : "correccion_id"
  parto ||--o{ correccion : "parto_id"
  usuario ||--o{ correccion : "aprobado_por"
  rancho ||--o{ sync_operacion : "rancho_id"
  usuario ||--o{ sync_operacion : "usuario_id"
```

Las mediciones usan kg (peso y peso_evaluacion) y cm (circunferencia_testicular).
El campo animal.circunferencia_testicular se conserva por compatibilidad con la API existente;
el historial de mediciones se registra en pesaje.

rancho.dias_lactancia acepta 60, 75 o 90; el valor predeterminado es 75.
Sexo, etapa de vida y estado reproductivo son atributos independientes.
Los animales no se eliminan: se registra una baja. Las correcciones son registros anexos inmutables.
foto.parto_id enlaza la evidencia del nacimiento; correccion_id es opcional para evidencia de correcciones.
tipo_pesaje es un catalogo adicional a las entidades del resumen de arquitectura.
