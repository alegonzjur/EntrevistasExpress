# 🔐 SISTEMA DE ROLES - GUÍA DE IMPLEMENTACIÓN

## Cambios Implementados en el Sistema de Reservas

---

## 📋 RESUMEN DE CAMBIOS

### **Sistema de Roles Implementado:**

1. ✅ **Rol Administrador**
   - Puede gestionar usuarios (crear, activar, desactivar, eliminar)
   - Puede cambiar roles de usuarios
   - Puede acceder al panel de administración
   - Puede hacer reservas como cualquier usuario

2. ✅ **Rol Profesor** (Usuario estándar)
   - Puede hacer reservas
   - Puede gestionar sus propias reservas
   - NO puede registrar nuevos usuarios
   - NO puede acceder al panel de administración

3. ✅ **Página de Login como página principal**
   - Ya no hay acceso público al registro
   - El registro solo es accesible para administradores

---

## 🗄️ CAMBIOS EN LA BASE DE DATOS

### **Nuevas Columnas en la Tabla `usuarios`:**

```sql
-- Ejecutar estos comandos SQL en tu base de datos PostgreSQL

-- 1. Añadir columna de rol (por defecto 'profesor')
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'profesor';

-- 2. Añadir columna de estado activo/inactivo (por defecto activo)
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;

-- 3. Añadir columna de fecha de creación
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 4. Si ya tienes usuarios existentes, actualizarlos para que sean profesores
UPDATE usuarios SET rol = 'profesor' WHERE rol IS NULL;
UPDATE usuarios SET activo = TRUE WHERE activo IS NULL;

-- 5. Crear usuario administrador inicial (si no existe)
-- IMPORTANTE: Cambia la contraseña después del primer login
INSERT INTO usuarios (username, email, password, rol, activo)
VALUES ('admin', 'admin@ejemplo.com', 'adminr€s3rv4s', 'admin', TRUE)
ON CONFLICT (username) DO NOTHING;
```

**NOTA:** El script de Python creará automáticamente el usuario admin con las credenciales:
- **Usuario:** `admin`
- **Contraseña:** `admin123`

⚠️ **IMPORTANTE: Cambia esta contraseña inmediatamente después del primer inicio de sesión**

---

## 📁 ARCHIVOS NUEVOS Y MODIFICADOS

### **Archivos Nuevos:**

1. **`app_roles.py`** - Versión actualizada de app.py con sistema de roles
2. **`admin_usuarios.html`** - Panel de gestión de usuarios
3. **`base_roles.html`** - Plantilla base actualizada con menú de administración
4. **`registro_admin.html`** - Formulario de registro solo para administradores
5. **`login_roles.html`** - Login actualizado sin enlace a registro público

### **Funcionalidades Nuevas en app.py:**

```python
# Decoradores de seguridad
@login_required  # Requiere estar logueado
@admin_required  # Requiere ser administrador

# Nuevas rutas de administración
/admin/usuarios                      # Lista de usuarios
/admin/usuario/toggle/<id>           # Activar/Desactivar usuario
/admin/usuario/eliminar/<id>         # Eliminar usuario
/admin/usuario/cambiar-rol/<id>      # Cambiar rol (admin ↔ profesor)
```

---

## 🚀 INSTALACIÓN Y CONFIGURACIÓN

### **Paso 1: Actualizar la Base de Datos**

```bash
# Conectar a PostgreSQL
psql -U usuario -d reservas_db

# Ejecutar los comandos SQL de la sección anterior
```

O usar Python directamente:

```python
# Opción alternativa: Ejecutar desde Python
python
>>> from app_roles import db, app
>>> with app.app_context():
...     db.session.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'profesor'")
...     db.session.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE")
...     db.session.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
...     db.session.commit()
>>> exit()
```

### **Paso 2: Reemplazar Archivos**

```bash
# Hacer backup de los archivos actuales
cp app.py app_backup.py
cp templates/base.html templates/base_backup.html
cp templates/registro.html templates/registro_backup.html
cp templates/login.html templates/login_backup.html

# Copiar los nuevos archivos
cp app_roles.py app.py
cp base_roles.html templates/base.html
cp registro_admin.html templates/registro.html
cp login_roles.html templates/login.html
cp admin_usuarios.html templates/admin_usuarios.html
```

### **Paso 3: Verificar y Ejecutar**

```bash
# Ejecutar la aplicación
python app.py
```

Al ejecutar, deberías ver:
```
✓ Usuario administrador creado: admin / admin123
✓ Días de la semana creados correctamente
```

### **Paso 4: Primer Login**

1. Ve a `http://localhost:5000`
2. Inicia sesión con:
   - **Usuario:** `admin`
   - **Contraseña:** `admin123`
3. **¡IMPORTANTE!** Cambia la contraseña del administrador inmediatamente

---

## 🎯 FUNCIONALIDADES DEL PANEL DE ADMINISTRACIÓN

### **1. Gestión de Usuarios** (`/admin/usuarios`)

**Acciones disponibles:**

#### **Activar/Desactivar Usuario**
- Desactiva temporalmente una cuenta sin eliminarla
- El usuario no podrá iniciar sesión mientras esté desactivado
- Sus reservas se mantienen intactas

#### **Cambiar Rol**
- Convierte un profesor en administrador (o viceversa)
- Útil para promocionar usuarios de confianza
- No puedes cambiar tu propio rol (seguridad)

#### **Eliminar Usuario**
- ⚠️ Acción irreversible
- Elimina el usuario y todas sus reservas
- Pide confirmación doble
- No puedes eliminarte a ti mismo

### **2. Crear Nuevo Usuario** (`/registro`)

- Solo accesible para administradores
- Formulario con validación
- Opciones:
  - Nombre de usuario (único)
  - Email (único)
  - Contraseña (mínimo 6 caracteres)
  - Rol (Profesor o Administrador)

---

## 🔒 SEGURIDAD IMPLEMENTADA

### **Protección de Rutas**

```python
# Ruta solo para usuarios autenticados
@app.route('/reservas')
@login_required
def reservas():
    # ...

# Ruta solo para administradores
@app.route('/admin/usuarios')
@admin_required
def admin_usuarios():
    # ...
```

### **Validaciones de Seguridad**

1. ✅ No puedes desactivar tu propia cuenta
2. ✅ No puedes eliminar tu propia cuenta
3. ✅ No puedes cambiar tu propio rol
4. ✅ Solo admins pueden cancelar reservas de otros
5. ✅ Las contraseñas se guardan hasheadas
6. ✅ Validación de sesiones en cada petición
7. ✅ Mensajes flash para feedback de acciones

---

## 🎨 CAMBIOS EN LA INTERFAZ

### **Navbar (Barra de Navegación)**

**Para Profesores:**
```
📅 Sistema de Reservas | 📅 Reservar | 📋 Mis Reservas | 👤 [Usuario] | Cerrar Sesión
```

**Para Administradores:**
```
📅 Sistema de Reservas | 📅 Reservar | 📋 Mis Reservas | ⚙️ Administración ▼ | 👤 [Usuario] [Admin] | Cerrar Sesión
                                                        ├─ 👥 Gestión de Usuarios
                                                        └─ ➕ Nuevo Usuario
```

### **Menú Desplegable de Administración**

- Hover sobre "⚙️ Administración" muestra opciones
- Acceso directo a gestión de usuarios
- Acceso rápido a crear nuevo usuario

### **Badge de Rol**

- Los administradores tienen un badge "Admin" visible
- Color: Blanco con fondo semi-transparente
- Visible en la barra de navegación

---

## 📊 ESTADÍSTICAS EN EL PANEL

El panel de administración muestra:

- **Total Usuarios:** Cuenta total de usuarios registrados
- **Administradores:** Número de usuarios con rol admin
- **Profesores:** Número de usuarios con rol profesor
- **Activos:** Usuarios que pueden iniciar sesión

---

## 🔄 FLUJO DE TRABAJO TÍPICO

### **Como Administrador:**

1. Login con credenciales de admin
2. Ir a "Administración" → "Nuevo Usuario"
3. Crear cuenta para un profesor:
   - Username: `juan.perez`
   - Email: `juan@colegio.com`
   - Contraseña: `temporal123`
   - Rol: Profesor
4. Entregar credenciales al profesor
5. (Opcional) Solicitar cambio de contraseña en primer login

### **Como Profesor:**

1. Recibir credenciales del administrador
2. Login en el sistema
3. Hacer reservas normalmente
4. Gestionar propias reservas
5. No ver opciones de administración

---

## ⚠️ CONSIDERACIONES IMPORTANTES

### **Seguridad:**

1. **Cambiar contraseña de admin:** La contraseña por defecto `admin123` debe cambiarse
2. **Crear al menos 2 administradores:** Para evitar quedar sin acceso si uno se desactiva
3. **No compartir credenciales:** Cada usuario debe tener su propia cuenta
4. **Revisar usuarios periódicamente:** Desactivar cuentas de usuarios que ya no necesitan acceso

### **Base de Datos:**

1. **Hacer backup antes de actualizar:** Siempre respaldar antes de modificar la estructura
2. **Verificar columnas nuevas:** Asegurarse de que las columnas se añadieron correctamente
3. **Actualizar usuarios existentes:** Si ya tienes usuarios, asignarles el rol 'profesor'

### **Usuarios Existentes:**

Si ya tienes usuarios en la base de datos antes de implementar roles:

```sql
-- Hacer que todos los usuarios existentes sean profesores
UPDATE usuarios SET rol = 'profesor' WHERE rol IS NULL;

-- Si quieres hacer admin a un usuario específico:
UPDATE usuarios SET rol = 'admin' WHERE username = 'nombre_usuario';
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### **Problema: "No tienes permisos para acceder a esta página"**
**Solución:** Tu usuario no tiene rol de administrador. Contacta con otro admin o actualiza manualmente en la BD:
```sql
UPDATE usuarios SET rol = 'admin' WHERE username = 'tu_usuario';
```

### **Problema: "Tu cuenta ha sido desactivada"**
**Solución:** Un administrador desactivó tu cuenta. Contacta con el admin para que la reactive.

### **Problema: No aparece el menú de administración**
**Solución:** Verifica que tu usuario tenga rol 'admin':
```sql
SELECT username, rol FROM usuarios WHERE username = 'tu_usuario';
```

### **Problema: Error al añadir columnas**
**Solución:** Es posible que las columnas ya existan. Usa `IF NOT EXISTS`:
```sql
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'profesor';
```

---

## 📝 CHECKLIST DE IMPLEMENTACIÓN

- [ ] Backup de la base de datos
- [ ] Backup de archivos actuales
- [ ] Añadir columnas a la tabla usuarios (rol, activo, fecha_creacion)
- [ ] Actualizar usuarios existentes con rol 'profesor'
- [ ] Copiar app_roles.py como app.py
- [ ] Copiar archivos HTML actualizados
- [ ] Ejecutar la aplicación y verificar usuario admin
- [ ] Login con admin/admin123
- [ ] Cambiar contraseña del admin
- [ ] Crear al menos 1 usuario profesor de prueba
- [ ] Verificar que el profesor NO ve el menú de administración
- [ ] Verificar que el profesor puede hacer reservas
- [ ] Verificar funcionalidades de admin (activar/desactivar/eliminar)
- [ ] Crear un segundo usuario admin (recomendado)

---

## 🎉 RESULTADO FINAL

Después de la implementación tendrás:

✅ Sistema de roles robusto (Admin/Profesor)
✅ Panel de administración completo
✅ Gestión de usuarios desde la interfaz
✅ Seguridad mejorada en las rutas
✅ Login como página principal
✅ Registro solo para administradores
✅ Feedback visual con mensajes flash
✅ Estadísticas de usuarios
✅ Control de usuarios activos/inactivos

---

## 📞 SOPORTE

Si tienes problemas durante la implementación:

1. Verifica que todas las columnas se añadieron correctamente
2. Revisa que el usuario admin se creó
3. Comprueba que los archivos se copiaron correctamente
4. Verifica los logs de la aplicación para errores específicos

¡El sistema está listo para gestionar usuarios de forma profesional! 🚀
