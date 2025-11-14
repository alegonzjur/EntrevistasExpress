# 📅 CAMBIO DE LÓGICA - SEMANAS DE CARGA Y ENTREVISTAS

## 🎯 NUEVO FUNCIONAMIENTO

### **Concepto:**
Los candidatos se cargan en una semana, pero las entrevistas se realizan en la **semana siguiente**.

```
Semana 45 (04-08 Nov)           Semana 46 (11-15 Nov)
├─ Lunes: Cargar Excel          ├─ Lunes: Entrevistas
├─ Martes: Procesar datos       ├─ Martes: Entrevistas
├─ Miércoles: Profesores        ├─ Miércoles: Entrevistas
│  reservan franjas W46         ├─ Jueves: Entrevistas
├─ Jueves: Ejecutar asignación  └─ Viernes: Entrevistas
└─ Viernes: Enviar emails

Candidatos W45 → Entrevistas W46
```

---

## 🔄 CAMBIOS REALIZADOS

### **Antes:**
```bash
python asignar_candidatos.py --semana 2024-W46
# Buscaba candidatos de W46 Y reservas de W46 (misma semana)
```

### **Ahora:**
```bash
python asignar_candidatos.py --semana-carga 2024-W45
# Busca candidatos de W45 Y reservas de W46 (semana siguiente)
```

---

## 📊 EJEMPLO PRÁCTICO

### **Lunes 04/11/2024 (Semana 45):**

**1. Cargar candidatos:**
```bash
python preprocesar_excel.py Calificaciones.xlsx --semana 2024-W45
```
✅ 5 candidatos guardados con `semana_carga = '2024-W45'`

---

### **Martes 05/11/2024 (Semana 45):**

**2. Profesores reservan franjas para la semana siguiente (W46):**
- Entran a la aplicación web
- Reservan franjas del 11-15 Nov (Semana 46)
- Ejemplo: Juan reserva Lunes 11/11 09:00-09:30

---

### **Miércoles 06/11/2024 (Semana 45):**

**3. Ejecutar asignación:**
```bash
python asignar_candidatos.py --semana-carga 2024-W45
```

**Lo que hace:**
- 📥 Busca candidatos con `semana_carga = '2024-W45'`
- 🔄 Calcula semana siguiente: `2024-W46`
- 📅 Busca reservas del 11-15 Nov (Semana 46)
- ✅ Asigna candidatos a esas reservas

**Salida del script:**
```
🎯 Asignador de Candidatos
📥 Semana de carga (candidatos): 2024-W45
📅 Semana de entrevistas (reservas): 2024-W46
======================================================================

📋 Cargando candidatos pendientes...
✅ 5 candidatos pendientes encontrados (semana carga: 2024-W45)

🔍 Buscando franjas reservadas disponibles...
   📅 Rango de fechas (semana entrevistas 2024-W46): 11/11/2024 - 15/11/2024
   🔖 Total de reservas encontradas: 12

✅ Asignación completada
```

---

## 🎯 VENTAJAS DEL NUEVO SISTEMA

### **1. Tiempo de Preparación:**
✅ Los profesores tienen toda una semana para reservar franjas
✅ No hay prisa el mismo día de las entrevistas

### **2. Notificación a Candidatos:**
✅ Los candidatos reciben email con una semana de antelación
✅ Tiempo suficiente para confirmar asistencia

### **3. Organización:**
✅ Proceso ordenado: cargar → reservar → asignar → notificar
✅ Separación clara de responsabilidades

---

## 📋 NUEVO WORKFLOW SEMANAL

### **SEMANA X (Preparación):**

**Lunes:**
```bash
# 1. Cargar candidatos
python preprocesar_excel.py Calificaciones.xlsx --semana 2024-WX
```

**Martes-Miércoles:**
- Profesores entran a la app
- Reservan franjas para SEMANA X+1

**Jueves:**
```bash
# 2. Ejecutar asignación
python asignar_candidatos.py --semana-carga 2024-WX

# 3. Enviar emails (futuro)
python enviar_emails.py --semana-carga 2024-WX
```

**Viernes:**
- Verificar asignaciones
- Candidatos confirman asistencia

---

### **SEMANA X+1 (Entrevistas):**

**Lunes-Viernes:**
- Entrevistas según las asignaciones
- Profesores registran resultados

---

## 🔧 USO DEL SCRIPT ACTUALIZADO

### **Sintaxis Nueva:**
```bash
python asignar_candidatos.py --semana-carga 2024-W45
```

### **Parámetros:**
- `--semana-carga`: Semana en que se cargaron los candidatos
- El script calcula automáticamente la semana siguiente para buscar reservas

### **Ejemplos:**
```bash
# Básico
python asignar_candidatos.py --semana-carga 2024-W45

# Con límite por profesor
python asignar_candidatos.py --semana-carga 2024-W45 --max-por-profesor 10

# Automático (sin confirmación)
python asignar_candidatos.py --semana-carga 2024-W45 --auto
```

---

## ✅ VERIFICACIÓN

### **Comprobar que todo está correcto:**

```sql
-- 1. Ver candidatos y su semana de carga
SELECT 
    semana_carga,
    COUNT(*) as candidatos,
    MIN(media_estudios) as nota_min,
    MAX(media_estudios) as nota_max
FROM candidatos
GROUP BY semana_carga
ORDER BY semana_carga DESC;

-- 2. Ver reservas por semana
SELECT 
    TO_CHAR(fecha, 'IYYY-"W"IW') as semana_reservas,
    COUNT(*) as total_reservas,
    MIN(fecha) as primera_fecha,
    MAX(fecha) as ultima_fecha
FROM reservas
GROUP BY TO_CHAR(fecha, 'IYYY-"W"IW')
ORDER BY semana_reservas DESC;

-- 3. Ver asignaciones con sus semanas
SELECT 
    c.semana_carga as semana_candidatos,
    TO_CHAR(r.fecha, 'IYYY-"W"IW') as semana_entrevistas,
    COUNT(a.id) as asignaciones
FROM asignaciones a
JOIN candidatos c ON a.candidato_id = c.id
JOIN reservas r ON a.reserva_id = r.id
GROUP BY c.semana_carga, TO_CHAR(r.fecha, 'IYYY-"W"IW')
ORDER BY c.semana_carga DESC;
```

**Resultado esperado:**
```
 semana_candidatos | semana_entrevistas | asignaciones
-------------------+--------------------+--------------
 2024-W45          | 2024-W46          |            5
```

---

## 🎯 TU CASO ACTUAL

### **Tu situación:**
- ✅ Candidatos cargados con `semana_carga = '2024-W45'`
- ✅ Necesitas reservas para semana `2024-W46` (11-15 Nov)

### **Solución:**

**1. Crear reservas para W46:**
```sql
-- Verificar si hay reservas para W46
SELECT COUNT(*) FROM reservas 
WHERE fecha BETWEEN '2024-11-11' AND '2024-11-15';
```

Si no hay, créalas en la aplicación web o:
```sql
INSERT INTO reservas (usuario_id, espacio_id, fecha, hora_inicio, hora_fin, notas)
VALUES 
    (1, 1, '2024-11-11', '09:00', '09:30', 'Entrevistas'),
    (1, 1, '2024-11-11', '09:30', '10:00', 'Entrevistas'),
    (1, 1, '2024-11-11', '10:00', '10:30', 'Entrevistas');
```

**2. Ejecutar asignación:**
```bash
python asignar_candidatos.py --semana-carga 2024-W45
```

**3. Verificar:**
```sql
SELECT 
    c.nombre || ' ' || c.apellidos as candidato,
    r.fecha,
    r.hora_inicio,
    a.posicion
FROM asignaciones a
JOIN candidatos c ON a.candidato_id = c.id
JOIN reservas r ON a.reserva_id = r.id
WHERE c.semana_carga = '2024-W45'
ORDER BY r.fecha, r.hora_inicio, a.posicion;
```

---

## 📚 RESUMEN

| Acción | Semana | Comando |
|--------|--------|---------|
| Cargar candidatos | W45 | `python preprocesar_excel.py archivo.xlsx --semana 2024-W45` |
| Reservar franjas | W45 | Profesores usan la app web para W46 |
| Asignar | W45 | `python asignar_candidatos.py --semana-carga 2024-W45` |
| Entrevistas | W46 | Candidatos asisten según asignaciones |

---

## 🎉 BENEFICIOS

✅ **Claridad:** Separación clara entre carga y entrevistas
✅ **Tiempo:** Una semana completa para preparar
✅ **Flexibilidad:** Profesores reservan con calma
✅ **Organización:** Proceso estructurado y predecible

---

¿Todo claro? Ahora puedes usar:

```bash
python asignar_candidatos.py --semana-carga 2024-W45
```

Y asignará tus candidatos de W45 a las reservas de W46! 🚀
