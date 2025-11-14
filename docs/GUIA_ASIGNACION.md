# 📖 GUÍA DE USO - ALGORITMO DE ASIGNACIÓN

## `asignar_candidatos.py`

Script que asigna automáticamente candidatos pendientes a franjas reservadas.

---

## 🎯 ¿QUÉ HACE EL SCRIPT?

1. ✅ Obtiene candidatos pendientes de la semana especificada
2. ✅ Busca franjas reservadas con espacios disponibles
3. ✅ Asigna **2 candidatos por franja** (15 minutos cada uno)
4. ✅ **Prioriza candidatos con menor nota** (más necesitados)
5. ✅ Balancea la carga entre entrevistadores
6. ✅ Respeta límite máximo por profesor (si se especifica)
7. ✅ Crea registros en `asignaciones`
8. ✅ Actualiza estado de candidatos a 'asignado'
9. ✅ Registra todo en `logs_asignacion`

---

## 🧠 LÓGICA DEL ALGORITMO

### **Orden de Asignación:**

```
Candidatos ordenados por NOTA (menor a mayor):
  1. Marina Igual (5.37)     ← Se asigna primero (más necesitada)
  2. Sandra Ehrmann (6.54)
  3. Esther Vázquez (6.78)
  4. Hafsa Belhadj (6.85)
  5. Katherine Gil (6.86)    ← Se asigna última

Franjas ordenadas por FECHA y HORA:
  1. Lunes 18/11 09:00-09:30 → [Marina, Sandra]
  2. Lunes 18/11 09:30-10:00 → [Esther, Hafsa]
  3. Lunes 18/11 10:00-10:30 → [Katherine]
```

### **Distribución en Franja:**

```
Franja: 09:00 - 09:30 (30 minutos)
├─ Posición 1: 09:00 - 09:15 (Candidato 1)
└─ Posición 2: 09:15 - 09:30 (Candidato 2)
```

---

## 📋 REQUISITOS PREVIOS

### **1. Candidatos en BD:**

```sql
-- Verificar candidatos pendientes
SELECT COUNT(*) FROM candidatos 
WHERE semana_carga = '2024-W46' 
AND estado = 'pendiente';
```

**Si no hay candidatos:** Ejecuta primero `preprocesar_excel.py`

---

### **2. Franjas Reservadas:**

Los profesores deben haber reservado franjas para esa semana en el sistema.

```sql
-- Verificar reservas de la semana
SELECT fecha, hora_inicio, hora_fin, u.username
FROM reservas r
JOIN usuarios u ON r.usuario_id = u.id
WHERE fecha BETWEEN '2024-11-18' AND '2024-11-22'
ORDER BY fecha, hora_inicio;
```

**Si no hay reservas:** Los profesores deben crear reservas en la aplicación web.

---

## 🚀 USO BÁSICO

### **1. Uso Simple:**

```bash
python asignar_candidatos.py --semana 2024-W46
```

**Resultado:**
- Carga candidatos pendientes
- Busca franjas disponibles
- Asigna automáticamente
- Muestra resumen
- Pide confirmación
- Guarda en BD

---

### **2. Modo Automático (Sin Confirmación):**

Útil para procesos batch o cron jobs:

```bash
python asignar_candidatos.py --semana 2024-W46 --auto
```

**⚠️ CUIDADO:** Guarda directamente sin pedir confirmación.

---

### **3. Limitar Candidatos por Profesor:**

Para balancear mejor la carga:

```bash
# Máximo 10 candidatos por profesor
python asignar_candidatos.py --semana 2024-W46 --max-por-profesor 10

# Máximo 5 por profesor
python asignar_candidatos.py --semana 2024-W46 --max-por-profesor 5
```

---

### **4. Especificar Admin:**

```bash
python asignar_candidatos.py --semana 2024-W46 --admin-id 1
```

---

## 📊 EJEMPLO DE EJECUCIÓN

```bash
$ python asignar_candidatos.py --semana 2024-W46

🎯 Asignador de Candidatos - Semana 2024-W46
📊 Máximo por profesor: 999
======================================================================

🚀 INICIANDO PROCESO DE ASIGNACIÓN AUTOMÁTICA
======================================================================

📋 Cargando candidatos pendientes...
✅ 5 candidatos pendientes encontrados
   📈 Rango de notas: 5.37 - 6.86

🔍 Buscando franjas reservadas disponibles...
   📅 Rango de fechas: 18/11/2024 - 22/11/2024
   🔖 Total de reservas encontradas: 12
✅ 10 franjas con espacios disponibles
   💺 Total de espacios disponibles: 20

🤖 Ejecutando algoritmo de asignación...

   🔄 Comenzando asignación de 5 candidatos...

✅ Asignación completada:
   • Candidatos asignados: 5
   • Candidatos sin asignar: 0
   • Franjas utilizadas: 3

📊 RESUMEN DE ASIGNACIONES (5):
======================================================================

👤 juan.perez (3 candidatos):
   • Marina Igual Paniagua (Nota: 5.37) - Pos 1
   • Sandra Beatriz Ehrmann de Corral (Nota: 6.54) - Pos 2
   • Esther Vázquez García (Nota: 6.78) - Pos 1

👤 maria.garcia (2 candidatos):
   • Hafsa Belhadj Díaz-Naranjo (Nota: 6.85) - Pos 1
   • Katherine Paula Gil Saavedra (Nota: 6.86) - Pos 2

======================================================================

❓ ¿Deseas guardar estas 5 asignaciones en la base de datos?
   Escribe 'SI' para confirmar: SI

💾 Guardando asignaciones en la base de datos...
✅ 5 asignaciones guardadas correctamente
✅ Log de asignación registrado

✅ PROCESO COMPLETADO EXITOSAMENTE
======================================================================
```

---

## ✅ VERIFICAR RESULTADOS EN BD

### **1. Ver Asignaciones Creadas:**

```sql
SELECT 
    a.id,
    c.nombre || ' ' || c.apellidos as candidato,
    c.media_estudios as nota,
    r.fecha,
    r.hora_inicio,
    a.posicion,
    a.minuto_inicio,
    u.username as entrevistador
FROM asignaciones a
JOIN candidatos c ON a.candidato_id = c.id
JOIN reservas r ON a.reserva_id = r.id
JOIN usuarios u ON a.entrevistador_id = u.id
WHERE c.semana_carga = '2024-W46'
ORDER BY r.fecha, r.hora_inicio, a.posicion;
```

**Resultado esperado:**
```
 id | candidato              | nota | fecha      | hora_inicio | posicion | entrevistador
----+------------------------+------+------------+-------------+----------+--------------
  1 | Marina Igual           | 5.37 | 2024-11-18 | 09:00:00    |        1 | juan.perez
  2 | Sandra Ehrmann         | 6.54 | 2024-11-18 | 09:00:00    |        2 | juan.perez
  3 | Esther Vázquez         | 6.78 | 2024-11-18 | 09:30:00    |        1 | juan.perez
  4 | Hafsa Belhadj          | 6.85 | 2024-11-18 | 10:00:00    |        1 | maria.garcia
  5 | Katherine Gil          | 6.86 | 2024-11-18 | 10:00:00    |        2 | maria.garcia
```

---

### **2. Ver Estados de Candidatos:**

```sql
-- Todos deben estar en 'asignado'
SELECT estado, COUNT(*) 
FROM candidatos 
WHERE semana_carga = '2024-W46'
GROUP BY estado;
```

**Resultado esperado:**
```
  estado   | count
-----------+-------
 asignado  |     5
```

---

### **3. Ver Log de Ejecución:**

```sql
SELECT * FROM logs_asignacion 
WHERE semana_objetivo = '2024-W46'
ORDER BY fecha_ejecucion DESC
LIMIT 1;
```

---

### **4. Conteo por Profesor:**

```sql
SELECT 
    u.username,
    COUNT(a.id) as total_asignaciones
FROM asignaciones a
JOIN usuarios u ON a.entrevistador_id = u.id
JOIN reservas r ON a.reserva_id = r.id
WHERE r.fecha BETWEEN '2024-11-18' AND '2024-11-22'
GROUP BY u.username
ORDER BY total_asignaciones DESC;
```

---

## ⚠️ CASOS ESPECIALES

### **1. No Hay Candidatos Pendientes:**

```bash
$ python asignar_candidatos.py --semana 2024-W46

📋 Cargando candidatos pendientes...
✅ 0 candidatos pendientes encontrados

⚠️  No hay candidatos pendientes para asignar
```

**Solución:** Ejecuta `preprocesar_excel.py` primero.

---

### **2. No Hay Franjas Disponibles:**

```bash
🔍 Buscando franjas reservadas disponibles...
   🔖 Total de reservas encontradas: 0
✅ 0 franjas con espacios disponibles

⚠️  No hay franjas disponibles
```

**Solución:** Los profesores deben crear reservas en la aplicación web.

---

### **3. Más Candidatos que Espacios:**

```bash
✅ Asignación completada:
   • Candidatos asignados: 15
   • Candidatos sin asignar: 5    ← Quedan sin asignar
   • Franjas utilizadas: 8
```

**Solución:** 
- Pedir a profesores que reserven más franjas
- O ejecutar de nuevo cuando haya más franjas

---

### **4. Ya Existen Asignaciones:**

El script respeta asignaciones previas y solo usa espacios libres:

```bash
🔍 Buscando franjas reservadas disponibles...
   🔖 Total de reservas encontradas: 12
✅ 8 franjas con espacios disponibles    ← 4 están llenas
   💺 Total de espacios disponibles: 12  ← 8 espacios ya ocupados
```

---

## 🔄 REASIGNAR CANDIDATOS

### **Si Algo Salió Mal:**

```sql
-- 1. Eliminar asignaciones de la semana
DELETE FROM asignaciones 
WHERE reserva_id IN (
    SELECT id FROM reservas 
    WHERE fecha BETWEEN '2024-11-18' AND '2024-11-22'
);

-- 2. Resetear estado de candidatos
UPDATE candidatos 
SET estado = 'pendiente'
WHERE semana_carga = '2024-W46';

-- 3. Volver a ejecutar
python asignar_candidatos.py --semana 2024-W46
```

---

## 🎯 WORKFLOW RECOMENDADO

### **Proceso Completo Semanal:**

```bash
# 1. Procesar Excel
python preprocesar_excel.py Calificaciones_semana46.xlsx --semana 2024-W46

# 2. Verificar candidatos
python -c "from sqlalchemy import create_engine; \
engine = create_engine('postgresql://postgres:postgres@localhost/reservas_db'); \
print(engine.execute('SELECT COUNT(*) FROM candidatos WHERE semana_carga = \"2024-W46\"').scalar())"

# 3. Los profesores reservan franjas en la web

# 4. Asignar automáticamente
python asignar_candidatos.py --semana 2024-W46

# 5. Verificar
psql -U postgres -d reservas_db -c "SELECT COUNT(*) FROM asignaciones WHERE reserva_id IN (SELECT id FROM reservas WHERE fecha BETWEEN '2024-11-18' AND '2024-11-22');"
```

---

## 🛠️ CONFIGURACIÓN AVANZADA

### **Cambiar Configuración:**

Edita `asignar_candidatos.py`:

```python
# Línea 29
CONFIG = {
    'max_candidatos_por_franja': 2,      # Cambiar a 3 o 4 si es necesario
    'minutos_por_entrevista': 15,        # Cambiar duración
    'max_por_profesor_default': 999,     # Límite por defecto
    'balance_tolerance': 0.2             # Tolerancia de balance
}
```

---

### **Cambiar Algoritmo:**

El algoritmo actual es **secuencial con prioridad por nota**. 

Para implementar otros algoritmos, modifica el método `asignar_candidatos()`:

- **Random**: `random.shuffle(self.candidatos_pendientes)`
- **Por nombre**: `order_by(Candidato.apellidos)`
- **Round-robin estricto**: Rotar entre profesores manualmente

---

## 📚 AYUDA DEL SCRIPT

```bash
python asignar_candidatos.py --help
```

**Salida:**
```
usage: asignar_candidatos.py [-h] --semana SEMANA [--max-por-profesor MAX]
                              [--auto] [--admin-id ID]

Asigna candidatos a franjas reservadas automáticamente

optional arguments:
  -h, --help            show this help message and exit
  --semana SEMANA       Semana a procesar (formato: 2024-W46)
  --max-por-profesor MAX
                        Máximo de candidatos por profesor
  --auto                Guardar automáticamente sin confirmación
  --admin-id ID         ID del usuario admin que ejecuta (default: 1)
```

---

## ✅ CHECKLIST DE EJECUCIÓN

- [ ] Candidatos procesados en BD (`preprocesar_excel.py`)
- [ ] Profesores han reservado franjas en la aplicación
- [ ] Verificar candidatos pendientes: `SELECT COUNT(*) FROM candidatos WHERE estado='pendiente' AND semana_carga='2024-W46'`
- [ ] Verificar franjas disponibles: `SELECT COUNT(*) FROM reservas WHERE fecha BETWEEN ...`
- [ ] Ejecutar script: `python asignar_candidatos.py --semana 2024-W46`
- [ ] Revisar resumen de asignaciones
- [ ] Confirmar con 'SI'
- [ ] Verificar en BD: `SELECT * FROM asignaciones`
- [ ] Verificar estados: `SELECT estado, COUNT(*) FROM candidatos GROUP BY estado`

---

## 🚀 PRÓXIMOS PASOS

Hemos completado:
1. ✅ Preprocesamiento de Excel
2. ✅ Asignación automática
3. ✅ Logs y auditoría

**Siguiente paso:**
- Integrar en la aplicación web (botón "Asignar automáticamente")
- Sistema de envío de emails a candidatos
- Vista de asignaciones en la web

---

¡El algoritmo está listo para usar! 🎉
