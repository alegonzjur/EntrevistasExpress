# 📦 GUÍA DE INSTALACIÓN - TABLAS DE CANDIDATOS

## Script SQL para PostgreSQL

---

## 🎯 ¿QUÉ CREA ESTE SCRIPT?

### **📊 4 Tablas Principales:**

1. **`candidatos`** - Información de candidatos importados del Excel
2. **`asignaciones`** - Relación candidato ↔ franja horaria (2 por franja)
3. **`logs_asignacion`** - Historial de ejecuciones del algoritmo
4. **`cargas_excel`** - Auditoría de archivos Excel subidos

### **🔍 1 Vista:**

- **`candidatos_con_asignacion`** - Vista completa con joins

### **⚙️ 2 Funciones:**

- **`obtener_candidatos_pendientes()`** - Lista de candidatos sin asignar
- **`estadisticas_semana(semana)`** - Estadísticas por semana

### **🔔 1 Trigger:**

- **`actualizar_estado_candidato`** - Cambia estado automáticamente

---

## 🚀 INSTALACIÓN PASO A PASO

### **OPCIÓN 1: Desde pgAdmin (GUI)**

1. **Abrir pgAdmin**
   - Conectar a tu servidor PostgreSQL
   - Seleccionar base de datos `reservas_db`

2. **Ejecutar el Script**
   - Click derecho en `reservas_db` → Query Tool
   - Abrir el archivo `crear_tablas_candidatos.sql`
   - Click en el botón ▶️ Execute
   - Esperar mensaje de confirmación

3. **Verificar Creación**
   - Refresh en `reservas_db` → Tables
   - Deberías ver las nuevas tablas

---

### **OPCIÓN 2: Desde Terminal/CMD (psql)**

```bash
# Navegar a la carpeta donde está el script
cd /ruta/al/script

# Ejecutar el script
psql -U usuario -d reservas_db -f crear_tablas_candidatos.sql

# O si tienes contraseña:
psql -U usuario -d reservas_db -W -f crear_tablas_candidatos.sql
```

**Reemplaza:**
- `usuario` → tu usuario de PostgreSQL (ej: `usuario`)
- `reservas_db` → nombre de tu base de datos

---

### **OPCIÓN 3: Desde Python (Automático)**

Si prefieres ejecutarlo desde Python:

```python
import psycopg2

# Conectar a la base de datos
conn = psycopg2.connect(
    host="localhost",
    database="reservas_db",
    user="usuario",
    password="usuario"
)

# Leer y ejecutar el script
with open('crear_tablas_candidatos.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

cursor = conn.cursor()
cursor.execute(sql_script)
conn.commit()

print("✅ Tablas creadas correctamente")

cursor.close()
conn.close()
```

---

## ✅ VERIFICACIÓN DE INSTALACIÓN

### **1. Verificar que las tablas existen:**

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('candidatos', 'asignaciones', 'logs_asignacion', 'cargas_excel')
ORDER BY table_name;
```

**Resultado esperado:**
```
 table_name      
-----------------
 asignaciones
 candidatos
 cargas_excel
 logs_asignacion
```

---

### **2. Verificar estructura de `candidatos`:**

```sql
\d candidatos
```

**Deberías ver:**
- 11 columnas
- Índices creados
- Constraints (checks, unique)

---

### **3. Probar funciones:**

```sql
-- Ver candidatos pendientes (debería estar vacío)
SELECT * FROM obtener_candidatos_pendientes();

-- Ver estadísticas de una semana (debería dar 0s)
SELECT * FROM estadisticas_semana('2024-W46');
```

---

### **4. Ver la vista:**

```sql
SELECT * FROM candidatos_con_asignacion;
```

Debería estar vacía por ahora.

---

## 📊 ESTRUCTURA DE LA TABLA `candidatos`

```
┌─────────────────┬──────────────┬─────────────┬─────────────┐
│ Columna         │ Tipo         │ Null?       │ Default     │
├─────────────────┼──────────────┼─────────────┼─────────────┤
│ id              │ SERIAL       │ NOT NULL    │ auto        │
│ solicitud       │ INTEGER      │ NOT NULL    │             │
│ apellidos       │ VARCHAR(150) │ NOT NULL    │             │
│ nombre          │ VARCHAR(100) │ NOT NULL    │             │
│ email           │ VARCHAR(120) │ NULL ✅     │             │
│ media_estudios  │ DECIMAL(4,2) │ NOT NULL    │             │
│ primera_opcion  │ TEXT         │             │             │
│ estado          │ VARCHAR(20)  │ NOT NULL    │ 'pendiente' │
│ fecha_carga     │ TIMESTAMP    │             │ NOW()       │
│ semana_carga    │ VARCHAR(20)  │             │             │
│ archivo_origen  │ VARCHAR(255) │             │             │
└─────────────────┴──────────────┴─────────────┴─────────────┘

Índices: 5
Constraints: 3
```

---

## 📊 ESTRUCTURA DE LA TABLA `asignaciones`

```
┌──────────────────────┬─────────────┬──────────┬─────────────────┐
│ Columna              │ Tipo        │ Null?    │ Default         │
├──────────────────────┼─────────────┼──────────┼─────────────────┤
│ id                   │ SERIAL      │ NOT NULL │ auto            │
│ candidato_id         │ INTEGER     │ NOT NULL │ FK→candidatos   │
│ reserva_id           │ INTEGER     │ NOT NULL │ FK→reservas     │
│ entrevistador_id     │ INTEGER     │ NOT NULL │ FK→usuarios     │
│ posicion             │ SMALLINT    │ NOT NULL │ 1 o 2           │
│ minuto_inicio        │ SMALLINT    │ NOT NULL │ 0 o 15          │
│ estado               │ VARCHAR(20) │ NOT NULL │ 'confirmado'    │
│ enviado_email        │ BOOLEAN     │          │ FALSE           │
│ fecha_email          │ TIMESTAMP   │ NULL     │                 │
│ resultado            │ TEXT        │ NULL     │                 │
│ notas_entrevista     │ TEXT        │ NULL     │                 │
│ fecha_asignacion     │ TIMESTAMP   │          │ NOW()           │
│ asignado_por_admin_id│ INTEGER     │ NULL     │ FK→usuarios     │
└──────────────────────┴─────────────┴──────────┴─────────────────┘

Constraint importante: 
- Un candidato solo puede tener 1 asignación activa
- Una posición (1 o 2) no puede duplicarse en la misma reserva
```

---

## 🎯 CASOS DE USO DE LAS FUNCIONES

### **Función: obtener_candidatos_pendientes()**

```sql
-- Ver candidatos que esperan asignación
SELECT * FROM obtener_candidatos_pendientes();
```

**Retorna:**
- id
- solicitud
- nombre_completo (nombre + apellidos)
- email
- media_estudios
- dias_desde_carga

**Útil para:**
- Ver quién espera asignación
- Ordenados por nota (más baja primero)
- Ver cuántos días llevan esperando

---

### **Función: estadisticas_semana()**

```sql
-- Ver estadísticas de la semana 46 de 2024
SELECT * FROM estadisticas_semana('2024-W46');
```

**Retorna:**
- total_candidatos
- candidatos_asignados
- candidatos_pendientes
- candidatos_entrevistados
- franjas_ocupadas
- tasa_ocupacion (%)

**Útil para:**
- Dashboard de admin
- Reportes semanales
- Seguimiento de progreso

---

## 🔔 TRIGGER AUTOMÁTICO

El trigger `actualizar_estado_candidato` funciona así:

```
Al CREAR asignación:
  candidato.estado = 'pendiente' → 'asignado' ✅

Al ELIMINAR asignación:
  candidato.estado = 'asignado' → 'pendiente' ✅
```

**No necesitas hacer nada manualmente**, el estado se actualiza solo.

---

## 📝 DATOS DE PRUEBA (Opcional)

Si quieres insertar los 5 candidatos del Excel de ejemplo:

```sql
INSERT INTO candidatos (solicitud, apellidos, nombre, email, media_estudios, primera_opcion, semana_carga, archivo_origen) VALUES
(73, 'Gil Saavedra', 'Katherine Paula', NULL, 6.86, 'Grado en Enfermería. CCS de Pº de la Habana. Madrid (Horario de mañana)', '2024-W46', 'Calificaciones_(9).xlsx'),
(7, 'Vázquez García', 'Esther', NULL, 6.78, 'Grado en Enfermería. CCS de Pº de la Habana. Madrid (Horario de mañana)', '2024-W46', 'Calificaciones_(9).xlsx'),
(54, 'Belhadj Díaz-Naranjo', 'Hafsa', NULL, 6.85, 'Grado en Enfermería. CCS de Ciempozuelos. Ciempozuelos Madrid (Horario de mañana)', '2024-W46', 'Calificaciones_(9).xlsx'),
(15, 'Igual Paniagua', 'Marina', NULL, 5.37, 'Grado en Enfermería. CCS de Ciempozuelos. Ciempozuelos Madrid (Horario de mañana)', '2024-W46', 'Calificaciones_(9).xlsx'),
(90, 'Ehrmann de Corral', 'Sandra Beatriz', NULL, 6.54, 'Grado en Fisioterapia. CCS de Pº de la Habana. Madrid (Horario de mañana)', '2024-W46', 'Calificaciones_(9).xlsx');

-- Verificar
SELECT id, solicitud, nombre, apellidos, media_estudios FROM candidatos;
```

---

## 🔧 COMANDOS ÚTILES

### **Ver todos los candidatos:**
```sql
SELECT * FROM candidatos ORDER BY media_estudios ASC;
```

### **Ver candidatos pendientes:**
```sql
SELECT * FROM candidatos WHERE estado = 'pendiente';
```

### **Ver asignaciones actuales:**
```sql
SELECT * FROM candidatos_con_asignacion WHERE estado_asignacion = 'confirmado';
```

### **Ver logs de asignaciones:**
```sql
SELECT * FROM logs_asignacion ORDER BY fecha_ejecucion DESC;
```

### **Eliminar todas las tablas nuevas (si necesitas empezar de cero):**
```sql
DROP TABLE IF EXISTS asignaciones CASCADE;
DROP TABLE IF EXISTS candidatos CASCADE;
DROP TABLE IF EXISTS logs_asignacion CASCADE;
DROP TABLE IF EXISTS cargas_excel CASCADE;
DROP VIEW IF EXISTS candidatos_con_asignacion CASCADE;
DROP FUNCTION IF EXISTS obtener_candidatos_pendientes() CASCADE;
DROP FUNCTION IF EXISTS estadisticas_semana(VARCHAR) CASCADE;
```

---

## ⚠️ NOTAS IMPORTANTES

### **1. Email Puede Ser NULL:**
```sql
-- Esto es válido:
INSERT INTO candidatos (..., email, ...) VALUES (..., NULL, ...);

-- O simplemente no incluir email:
INSERT INTO candidatos (solicitud, apellidos, nombre, media_estudios, ...)
VALUES (123, 'Pérez', 'Juan', 6.50, ...);
```

### **2. Constraint de Duplicados:**
```sql
-- No puedes insertar el mismo solicitud + semana_carga dos veces
CONSTRAINT unq_solicitud_semana UNIQUE(solicitud, semana_carga)
```

**Ejemplo de error:**
```sql
-- Primera vez: OK ✅
INSERT INTO candidatos (solicitud, apellidos, nombre, media_estudios, semana_carga)
VALUES (73, 'Gil', 'Katherine', 6.86, '2024-W46');

-- Segunda vez: ERROR ❌
INSERT INTO candidatos (solicitud, apellidos, nombre, media_estudios, semana_carga)
VALUES (73, 'Gil', 'Katherine', 6.86, '2024-W46');
-- ERROR: duplicate key value violates unique constraint
```

### **3. Estados Válidos:**

**Para candidatos:**
- `pendiente` (default)
- `asignado`
- `entrevistado`
- `ausente`
- `cancelado`

**Para asignaciones:**
- `confirmado` (default)
- `cancelado`
- `completado`
- `ausente`

---

## ✅ CHECKLIST DE INSTALACIÓN

- [ ] Script SQL ejecutado sin errores
- [ ] 4 tablas creadas (candidatos, asignaciones, logs_asignacion, cargas_excel)
- [ ] 1 vista creada (candidatos_con_asignacion)
- [ ] 2 funciones creadas (obtener_candidatos_pendientes, estadisticas_semana)
- [ ] 1 trigger creado (actualizar_estado_candidato)
- [ ] Verificación: `SELECT * FROM obtener_candidatos_pendientes();` ejecuta sin error
- [ ] Opcional: Datos de prueba insertados

---

## 🚀 PRÓXIMO PASO

Una vez instaladas las tablas, el siguiente paso es:

**Actualizar los modelos SQLAlchemy en `app.py`**

Esto permitirá que la aplicación Flask interactúe con las nuevas tablas.

---

## 📞 SOLUCIÓN DE PROBLEMAS

### **Error: "relation already exists"**
```
ERROR:  relation "candidatos" already exists
```
**Solución:** Las tablas ya existen. Si quieres recrearlas:
```sql
DROP TABLE IF EXISTS asignaciones CASCADE;
DROP TABLE IF EXISTS candidatos CASCADE;
-- etc...
```
Luego ejecuta el script de nuevo.

---

### **Error: "permission denied"**
```
ERROR:  permission denied for schema public
```
**Solución:** Tu usuario no tiene permisos. Ejecuta como superusuario o pide permisos al DBA.

---

### **Error: "database does not exist"**
```
FATAL:  database "reservas_db" does not exist
```
**Solución:** Verifica el nombre de la base de datos o créala primero.

---

¡Listo! Una vez ejecutado el script, tendrás toda la infraestructura de base de datos lista para el sistema de candidatos. 🎉
