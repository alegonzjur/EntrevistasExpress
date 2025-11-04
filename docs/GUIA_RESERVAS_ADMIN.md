# 👥 RESERVAS EN NOMBRE DE OTROS USUARIOS

## Nueva Funcionalidad para Administradores

---

## 📋 RESUMEN

Los **administradores** ahora pueden crear reservas en nombre de cualquier profesor (usuario estándar). Esto es útil cuando:

- Un profesor solicita una reserva por teléfono o email
- Necesitas organizar horarios para todo el equipo
- Un profesor tiene problemas técnicos para reservar
- Quieres gestionar todas las reservas de forma centralizada

---

## 🎯 ¿CÓMO FUNCIONA?

### **Para Administradores:**

1. **Iniciar sesión** como administrador
2. **Ir a la página de Reservas** (📅 Reservar)
3. **Seleccionar usuario** en el desplegable "👤 Reservar para:"
   - Por defecto: "Yo mismo (admin)"
   - Opciones: Todos los usuarios activos del sistema
4. **Aparece badge "⚠️ Modo Admin"** cuando reservas para otro
5. **Hacer la reserva** normalmente (seleccionar día y franja)
6. **Modal de confirmación** muestra para quién se está reservando

### **Para Profesores:**

- ❌ **NO ven** el selector de usuarios
- ✅ Solo pueden reservar para sí mismos
- ✅ Ven normalmente todas sus reservas
- ✅ No hay cambios en su experiencia

---

## 🔧 INSTALACIÓN

### **Paso 1: Actualizar Base de Datos**

Ejecuta el script SQL:

```bash
psql -U usuario -d reservas_db -f actualizacion_reserva_admin.sql
```

O manualmente:

```sql
ALTER TABLE reservas 
ADD COLUMN IF NOT EXISTS creado_por_admin INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_reservas_creado_por_admin 
ON reservas(creado_por_admin);
```

### **Paso 2: Actualizar Archivos**

```bash
# Hacer backup
cp app.py app_backup_$(date +%Y%m%d).py
cp templates/reservas.html templates/reservas_backup_$(date +%Y%m%d).html

# Copiar nuevos archivos
cp app_reserva_admin.py app.py
cp reservas.html templates/
```

### **Paso 3: Reiniciar la Aplicación**

```bash
python app.py
```

---

## 🎨 INTERFAZ DE USUARIO

### **Vista de Administrador:**

```
┌─────────────────────────────────────────────────────────────┐
│ 📅 Reservar Franjas Horarias                                │
│                                                              │
│  [📋 Mis Reservas] [📆 Semana Actual]                       │
│                                                              │
│  👤 Reservar para: [Yo mismo (admin)        ▼] ⚠️ Modo Admin│
│                    ├─ juan.perez                             │
│                    ├─ maria.garcia                           │
│                    └─ pedro.lopez                            │
│                                                              │
│  [← Semana Anterior]  Semana del 04/11/2025  [Semana →]    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Lunes                              04/11/2025        │   │
│  │ [09:00] [09:30] [10:00] [10:30] ...                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### **Vista de Profesor:**

```
┌─────────────────────────────────────────────────────────────┐
│ 📅 Reservar Franjas Horarias                                │
│                                                              │
│  [📋 Mis Reservas] [📆 Semana Actual]                       │
│                                                              │
│  [← Semana Anterior]  Semana del 04/11/2025  [Semana →]    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Lunes                              04/11/2025        │   │
│  │ [09:00] [09:30] [10:00] [10:30] ...                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📱 FLUJO DE USO

### **Caso de Uso 1: Reservar para ti mismo (Admin)**

1. Selector muestra: "Yo mismo (admin)"
2. Badge "Modo Admin" está oculto
3. Seleccionar franja horaria
4. Modal muestra: "Día: Lunes, Horario: 10:00 - 10:30"
5. Confirmar reserva
6. ✅ Reserva creada a nombre del admin

### **Caso de Uso 2: Reservar para un profesor**

1. Cambiar selector a: "juan.perez (juan@colegio.com)"
2. Badge "⚠️ Modo Admin" aparece (color amarillo)
3. Seleccionar franja horaria
4. Modal muestra:
   ```
   ⚠️ Reservando para: juan.perez (juan@colegio.com)
   Día: Lunes
   Horario: 10:00 - 10:30
   ```
5. Confirmar reserva
6. ✅ Mensaje: "Reserva creada correctamente para juan.perez"
7. La reserva aparece en "Mis Reservas" de juan.perez

---

## 🔍 DETALLES TÉCNICOS

### **Nueva Columna en la Base de Datos:**

```sql
creado_por_admin INTEGER REFERENCES usuarios(id)
```

- **NULL**: Reserva creada por el propio usuario
- **ID del admin**: Reserva creada por un administrador

### **Ejemplos de Consultas:**

**Ver quién creó cada reserva:**

```sql
SELECT 
    u_reserva.username AS para_usuario,
    COALESCE(u_admin.username, 'El mismo usuario') AS creado_por,
    r.fecha,
    r.hora_inicio
FROM reservas r
JOIN usuarios u_reserva ON r.usuario_id = u_reserva.id
LEFT JOIN usuarios u_admin ON r.creado_por_admin = u_admin.id
ORDER BY r.fecha DESC;
```

**Reservas creadas por administradores:**

```sql
SELECT 
    COUNT(*) as total,
    u_admin.username as administrador
FROM reservas r
JOIN usuarios u_admin ON r.creado_por_admin = u_admin.id
GROUP BY u_admin.username;
```

---

## 🎯 CARACTERÍSTICAS CLAVE

### **Seguridad:**

- ✅ Solo administradores pueden reservar para otros
- ✅ Profesores no ven el selector de usuarios
- ✅ Validación en el backend (no solo frontend)
- ✅ Los profesores solo pueden cancelar sus propias reservas
- ✅ Los admins pueden cancelar cualquier reserva

### **Auditoría:**

- ✅ Se registra quién creó cada reserva
- ✅ Puedes saber si una reserva la hizo el usuario o un admin
- ✅ Consultas SQL disponibles para reportes

### **Experiencia de Usuario:**

- ✅ Badge visual cuando estás en "Modo Admin"
- ✅ Confirmación clara de para quién reservas
- ✅ Mensajes personalizados según quién reserva
- ✅ Interfaz intuitiva y sin complicaciones

---

## 📊 CASOS DE USO REALES

### **Escenario 1: Secretaría Escolar**

**Situación:** Los profesores llaman a secretaría para reservar espacios

**Solución:**
1. Admin inicia sesión
2. Selecciona al profesor en el desplegable
3. Reserva en su nombre
4. El profesor ve la reserva en su cuenta

### **Escenario 2: Coordinador de Departamento**

**Situación:** Necesitas organizar reuniones para todo el equipo

**Solución:**
1. Admin crea una tabla con las franjas
2. Va reservando una a una para cada profesor
3. Cada profesor recibe su asignación automáticamente

### **Escenario 3: Soporte Técnico**

**Situación:** Un profesor tiene problemas para acceder al sistema

**Solución:**
1. Llama al admin
2. Admin hace la reserva en su nombre
3. Problema resuelto sin esperar

---

## ⚙️ CONFIGURACIÓN AVANZADA

### **Personalizar el Selector:**

Edita `reservas.html` línea ~380:

```html
<select id="usuario-selector" onchange="cambiarModoReserva()">
    <option value="{{ session.user_id }}" selected>
        Yo mismo ({{ session.username }})
    </option>
    {% for usuario in usuarios_lista %}
        {% if usuario.id != session.user_id %}
        <option value="{{ usuario.id }}">
            {{ usuario.username }} ({{ usuario.email }})
        </option>
        {% endif %}
    {% endfor %}
</select>
```

### **Cambiar el Badge "Modo Admin":**

Edita los estilos en `reservas.html`:

```css
.badge-admin-mode {
    padding: 6px 12px;
    background: #f59e0b;  /* Cambiar color aquí */
    color: white;
    border-radius: 15px;
    font-size: 12px;
    font-weight: 600;
}
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### **Problema: No veo el selector de usuarios**

**Causas posibles:**
1. No has iniciado sesión como administrador
2. Tu usuario no tiene rol 'admin'

**Solución:**
```sql
UPDATE usuarios SET rol = 'admin' WHERE username = 'tu_usuario';
```

### **Problema: Error al crear reserva para otro usuario**

**Causas posibles:**
1. La columna `creado_por_admin` no existe
2. No ejecutaste el script SQL

**Solución:**
```sql
ALTER TABLE reservas 
ADD COLUMN IF NOT EXISTS creado_por_admin INTEGER REFERENCES usuarios(id);
```

### **Problema: El selector está vacío**

**Causas posibles:**
1. No hay otros usuarios en el sistema
2. Todos los usuarios están desactivados

**Solución:**
- Crear más usuarios desde el panel de administración
- Activar usuarios existentes

---

## 📈 ESTADÍSTICAS Y REPORTES

### **Cuántas reservas ha hecho el admin para otros:**

```sql
SELECT 
    COUNT(*) as reservas_delegadas
FROM reservas 
WHERE creado_por_admin IS NOT NULL;
```

### **Usuarios que más reciben reservas de admins:**

```sql
SELECT 
    u.username,
    COUNT(r.id) as reservas_recibidas
FROM usuarios u
JOIN reservas r ON u.id = r.usuario_id
WHERE r.creado_por_admin IS NOT NULL
GROUP BY u.username
ORDER BY reservas_recibidas DESC;
```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

- [ ] Ejecutar script SQL para añadir columna `creado_por_admin`
- [ ] Actualizar `app.py` con la nueva versión
- [ ] Actualizar `reservas.html` con el selector
- [ ] Reiniciar la aplicación
- [ ] Verificar que el admin ve el selector
- [ ] Verificar que los profesores NO ven el selector
- [ ] Probar crear reserva para ti mismo
- [ ] Probar crear reserva para otro usuario
- [ ] Verificar que la reserva aparece en "Mis Reservas" del usuario
- [ ] Probar cancelar una reserva creada por admin

---

## 🎉 BENEFICIOS

✅ **Centralización:** Gestión unificada de todas las reservas
✅ **Flexibilidad:** Atender solicitudes por múltiples canales
✅ **Eficiencia:** Resolver problemas sin esperar a que el usuario lo haga
✅ **Control:** Los admins tienen visibilidad completa
✅ **Auditoría:** Saber quién creó cada reserva
✅ **Escalabilidad:** Funciona con cualquier número de usuarios

---

¡La funcionalidad está lista para usarse! 🚀
