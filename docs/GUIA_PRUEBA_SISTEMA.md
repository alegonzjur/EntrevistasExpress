# 🚀 GUÍA RÁPIDA - AÑADIR BOTÓN Y PROBAR SISTEMA

## 📁 ARCHIVOS GENERADOS

1. **candidatos_prueba_semana47.xlsx** - Excel con 12 candidatos
2. **ejemplo_base_template.html** - Template base completo con menú
3. Esta guía

---

## 📊 DATOS DEL EXCEL

**Archivo:** `candidatos_prueba_semana47.xlsx`

**Candidatos:** 12 personas
**Notas:** 5.13 - 6.91
**Semana:** 47 (17-21 Noviembre 2025)

**Contenido:**
- Fila 24 = Encabezados
- Filas 25-36 = 12 candidatos
- Todos con nota < 7.0 (aptos para importar)

---

## 🔘 AÑADIR BOTÓN DE CANDIDATOS

### **OPCIÓN 1: Menú Dropdown (Recomendada)**

Edita tu `templates/base.html` y añade en el menú de navegación:

```html
{% if es_admin %}
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="navbarDropdownAdmin" 
       role="button" data-bs-toggle="dropdown" aria-expanded="false">
        <i class="fas fa-cog"></i> Administración
    </a>
    <ul class="dropdown-menu" aria-labelledby="navbarDropdownAdmin">
        <li><a class="dropdown-item" href="{{ url_for('admin_usuarios') }}">
            <i class="fas fa-users-cog"></i> Usuarios
        </a></li>
        <li><a class="dropdown-item" href="{{ url_for('admin_estadisticas') }}">
            <i class="fas fa-chart-bar"></i> Estadísticas
        </a></li>
        <li><a class="dropdown-item" href="{{ url_for('todas_reservas') }}">
            <i class="fas fa-calendar-alt"></i> Todas las Reservas
        </a></li>
        <li><hr class="dropdown-divider"></li>
        <li><a class="dropdown-item" href="{{ url_for('admin_candidatos') }}">
            <i class="fas fa-user-graduate"></i> Gestión de Candidatos
        </a></li>
    </ul>
</li>
{% endif %}
```

---

### **OPCIÓN 2: Enlace Simple**

Si prefieres un enlace directo:

```html
{% if es_admin %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('admin_candidatos') }}">
        <i class="fas fa-user-graduate"></i> Candidatos
    </a>
</li>
{% endif %}
```

---

### **OPCIÓN 3: Botón Flotante (Más Visual)**

Añade al final de `templates/reservas.html`:

```html
{% if es_admin %}
<!-- Botón Flotante para Candidatos -->
<a href="{{ url_for('admin_candidatos') }}" 
   class="btn btn-primary btn-floating" 
   title="Gestión de Candidatos">
    <i class="fas fa-user-graduate fa-2x"></i>
</a>

<style>
.btn-floating {
    position: fixed;
    bottom: 30px;
    right: 30px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    z-index: 1000;
    transition: all 0.3s ease;
}

.btn-floating:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
}
</style>
{% endif %}
```

---

## ✅ ESTILOS - VERIFICAR BASE.HTML

Tu `base.html` debe incluir:

### **1. Bootstrap 5:**
```html
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
```

### **2. Font Awesome:**
```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
```

### **3. JavaScript de Bootstrap:**
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

**Si no los tienes**, puedes usar el `ejemplo_base_template.html` como referencia.

---

## 🧪 PROCESO DE PRUEBA COMPLETO

### **PASO 1: Crear Reservas para Semana 47**

Las entrevistas serán en la **semana 47** (17-21 Nov).

**Opción A: Desde la aplicación web**

1. Ir a la semana del 17-21 Nov en el calendario
2. Crear reservas de media hora
3. Ejemplo:
   - Lunes 17/11: 09:00-09:30, 09:30-10:00, 10:00-10:30
   - Martes 18/11: 09:00-09:30, 09:30-10:00
   - Miércoles 19/11: 09:00-09:30

**Opción B: SQL directo**

```sql
-- Asegúrate de que existen usuarios (por ejemplo, id=1)
-- Crear 6 reservas para la semana 47

INSERT INTO reservas (usuario_id, espacio_id, fecha, hora_inicio, hora_fin, notas)
VALUES 
    (1, 1, '2025-11-17', '09:00', '09:30', 'Entrevistas Semana 47'),
    (1, 1, '2025-11-17', '09:30', '10:00', 'Entrevistas Semana 47'),
    (1, 1, '2025-11-17', '10:00', '10:30', 'Entrevistas Semana 47'),
    (1, 2, '2025-11-18', '09:00', '09:30', 'Entrevistas Semana 47'),
    (1, 2, '2025-11-18', '09:30', '10:00', 'Entrevistas Semana 47'),
    (1, 3, '2025-11-19', '09:00', '09:30', 'Entrevistas Semana 47');

-- Verificar
SELECT fecha, hora_inicio, hora_fin FROM reservas 
WHERE fecha BETWEEN '2025-11-17' AND '2025-11-21'
ORDER BY fecha, hora_inicio;
```

---

### **PASO 2: Cargar Excel**

1. **Acceder:**
   ```
   http://localhost:5000/admin/candidatos
   ```

2. **Cargar Archivo:**
   - Click "Examinar"
   - Seleccionar: `candidatos_prueba_semana47.xlsx`
   - Semana: **Semana 46** (10/11 - 14/11) ← Importante!
   - Umbral: 7.0
   - Click "Cargar y Procesar"

3. **Resultado Esperado:**
   ```
   ✅ ¡Éxito!
   12 candidatos importados correctamente
   - Total leídos: 12
   - Válidos: 12
   - Importados (nota < 7.0): 12
   - Semana: 2024-W46
   ```

---

### **PASO 3: Ejecutar Asignación**

1. **En la misma página:**
   - Sección "Asignación Automática"
   - Semana de Carga: **Semana 46**
   - Max por profesor: (dejar vacío o poner 10)
   - Click "Ejecutar Asignación"

2. **Confirmación:**
   ```
   ¿Estás seguro de ejecutar la asignación automática?
   [Aceptar]
   ```

3. **Resultado Esperado:**
   ```
   ✅ ¡Asignación Completada!
   12 candidatos asignados correctamente
   - Candidatos asignados: 12
   - Franjas utilizadas: 6
   - Semana carga: 2024-W46
   - Semana entrevistas: 2024-W47
   - Tiempo: 0.15s
   ```

---

### **PASO 4: Verificar Resultados**

#### **4.1 Ver Candidatos:**

Click "Ver Candidatos" en la fila de Semana 46

**Deberías ver:**
- Total: 12
- Estado: Todos "Asignado" (badge verde)
- Filtros funcionales
- Exportar CSV funcional

#### **4.2 Ver Asignaciones:**

Click "Ver Asignaciones" en la fila de Semana 46

**Deberías ver:**
- Total asignaciones: 12
- Franjas ocupadas: 6
- Entrevistadores: (según tus usuarios)
- Vista Tabla con todos los detalles
- Vista Calendario por días

#### **4.3 Verificar en Base de Datos:**

```sql
-- Ver candidatos
SELECT 
    solicitud, 
    nombre, 
    apellidos, 
    media_estudios, 
    estado, 
    semana_carga
FROM candidatos
ORDER BY media_estudios;

-- Ver asignaciones
SELECT 
    c.nombre || ' ' || c.apellidos as candidato,
    c.media_estudios as nota,
    r.fecha,
    r.hora_inicio,
    a.posicion,
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
candidato          | nota | fecha      | hora | pos | entrevistador
-------------------+------+------------+------+-----+--------------
Carmen Ruiz        | 5.13 | 2025-11-17 | 9:00 |  1  | admin
María José López   | 5.25 | 2025-11-17 | 9:00 |  2  | admin
Laura García       | 5.42 | 2025-11-17 | 9:30 |  1  | admin
...
```

---

## 🎯 RESULTADO FINAL

Deberías tener:

✅ **12 candidatos** cargados en BD con semana_carga = '2024-W46'
✅ **12 asignaciones** a reservas de semana 47 (17-21 Nov)
✅ **6 franjas** ocupadas (2 candidatos por franja)
✅ **Vista visual** de todo en la web

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### **Error: "No hay candidatos pendientes"**

**Causa:** La semana no coincide.

**Solución:**
```sql
SELECT semana_carga, COUNT(*) FROM candidatos GROUP BY semana_carga;
```
Usa la semana correcta en "Ejecutar Asignación"

---

### **Error: "No hay reservas disponibles"**

**Causa:** No hay reservas para la semana siguiente.

**Solución:**
- Candidatos están en W46
- Necesitas reservas en W47 (17-21 Nov)
```sql
SELECT fecha, COUNT(*) FROM reservas 
WHERE fecha BETWEEN '2025-11-17' AND '2025-11-21'
GROUP BY fecha;
```

---

### **Error al cargar Excel**

**Causa:** Columnas incorrectas

**Solución:** El Excel tiene las columnas exactas:
- Solicitud
- Apellidos
- Nombre
- Media estudios realizados
- Primera opción

---

### **Botón de Candidatos no aparece**

**Causa:** Falta `es_admin` en el contexto

**Solución:** En `app.py`, asegúrate de pasar `es_admin`:
```python
return render_template('reservas.html', 
                     ...,
                     es_admin=session.get('rol') == 'admin')
```

---

## 📋 CHECKLIST FINAL

Antes de probar:

- [ ] Base.html tiene Bootstrap 5
- [ ] Base.html tiene Font Awesome
- [ ] Botón "Candidatos" añadido al menú
- [ ] Rutas de candidatos integradas en app.py
- [ ] Templates copiados a /templates
- [ ] Excel descargado
- [ ] Reservas creadas para W47 (17-21 Nov)
- [ ] Usuario admin logueado

Ahora a probar:

- [ ] Cargar Excel con semana 46
- [ ] Ver candidatos importados
- [ ] Ejecutar asignación
- [ ] Ver asignaciones creadas
- [ ] Verificar en BD
- [ ] Probar filtros y exportación

---

## 🎉 ¡LISTO!

Tienes todo para probar el sistema completo:

1. 📥 Excel con candidatos
2. 🔘 Botón en el menú
3. 🎨 Estilos correctos
4. 📅 Reservas para la semana correcta

**Siguiente paso:** ¡Pruébalo! 🚀
