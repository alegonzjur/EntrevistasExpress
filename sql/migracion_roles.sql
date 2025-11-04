-- ====================================================================
-- SCRIPT DE MIGRACIÓN: SISTEMA DE ROLES
-- Sistema de Reservas - Base de datos PostgreSQL
-- ====================================================================
-- 
-- Este script añade las columnas necesarias para el sistema de roles
-- y crea el usuario administrador inicial.
--
-- IMPORTANTE: Ejecutar este script ANTES de usar la nueva versión de app.py
-- ====================================================================

-- 1. AÑADIR COLUMNAS A LA TABLA USUARIOS
-- ====================================================================

-- Columna ROL: Define si el usuario es 'admin' o 'profesor'
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'profesor';

-- Columna ACTIVO: Indica si el usuario puede iniciar sesión
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;

-- Columna FECHA_CREACION: Registra cuándo se creó el usuario
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Columna NOTAS en la tabla RESERVAS (si no existe)
ALTER TABLE reservas 
ADD COLUMN IF NOT EXISTS notas TEXT;

-- Columna COLOR en la tabla ESPACIOS (si no existe)
ALTER TABLE espacios 
ADD COLUMN IF NOT EXISTS color VARCHAR(7) DEFAULT '#667eea';


-- 2. ACTUALIZAR USUARIOS EXISTENTES
-- ====================================================================

-- Asignar rol 'profesor' a todos los usuarios existentes que no tengan rol
UPDATE usuarios 
SET rol = 'profesor' 
WHERE rol IS NULL OR rol = '';

-- Activar todos los usuarios existentes
UPDATE usuarios 
SET activo = TRUE 
WHERE activo IS NULL;

-- Establecer fecha de creación para usuarios sin fecha
UPDATE usuarios 
SET fecha_creacion = CURRENT_TIMESTAMP 
WHERE fecha_creacion IS NULL;


-- 3. CREAR USUARIO ADMINISTRADOR INICIAL
-- ====================================================================

-- NOTA: La contraseña 'admin123' está hasheada con werkzeug
-- Debes cambiarla inmediatamente después del primer login

-- Opción A: Si ya existe un usuario que quieres hacer admin
-- Descomenta y cambia 'nombre_usuario' por tu usuario:
-- UPDATE usuarios SET rol = 'admin' WHERE username = 'nombre_usuario';

-- Opción B: El usuario admin se creará automáticamente al ejecutar app.py
-- Usuario: admin
-- Contraseña: admin123 (¡CÁMBIALA INMEDIATAMENTE!)


-- 4. VERIFICACIÓN
-- ====================================================================

-- Verificar que las columnas se añadieron correctamente
SELECT 
    column_name, 
    data_type, 
    column_default
FROM information_schema.columns 
WHERE table_name = 'usuarios' 
  AND column_name IN ('rol', 'activo', 'fecha_creacion')
ORDER BY ordinal_position;

-- Mostrar todos los usuarios y sus roles
SELECT 
    id,
    username,
    email,
    rol,
    activo,
    fecha_creacion
FROM usuarios
ORDER BY fecha_creacion DESC;

-- Contar usuarios por rol
SELECT 
    rol,
    COUNT(*) as total
FROM usuarios
GROUP BY rol;


-- 5. COMANDOS ÚTILES PARA GESTIÓN
-- ====================================================================

-- Hacer administrador a un usuario específico:
-- UPDATE usuarios SET rol = 'admin' WHERE username = 'nombre_usuario';

-- Hacer profesor a un usuario específico:
-- UPDATE usuarios SET rol = 'profesor' WHERE username = 'nombre_usuario';

-- Desactivar un usuario:
-- UPDATE usuarios SET activo = FALSE WHERE username = 'nombre_usuario';

-- Activar un usuario:
-- UPDATE usuarios SET activo = TRUE WHERE username = 'nombre_usuario';

-- Ver solo administradores:
-- SELECT username, email, activo FROM usuarios WHERE rol = 'admin';

-- Ver solo profesores:
-- SELECT username, email, activo FROM usuarios WHERE rol = 'profesor';

-- Ver usuarios inactivos:
-- SELECT username, email, rol FROM usuarios WHERE activo = FALSE;


-- 6. ÍNDICES PARA MEJORAR RENDIMIENTO (OPCIONAL)
-- ====================================================================

-- Índice en la columna rol para búsquedas más rápidas
CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios(rol);

-- Índice en la columna activo
CREATE INDEX IF NOT EXISTS idx_usuarios_activo ON usuarios(activo);

-- Índice compuesto para búsquedas de usuarios activos por rol
CREATE INDEX IF NOT EXISTS idx_usuarios_rol_activo ON usuarios(rol, activo);


-- ====================================================================
-- FIN DEL SCRIPT
-- ====================================================================

-- RESUMEN DE CAMBIOS:
-- ✓ Columna 'rol' añadida a usuarios (admin/profesor)
-- ✓ Columna 'activo' añadida a usuarios (true/false)
-- ✓ Columna 'fecha_creacion' añadida a usuarios
-- ✓ Columna 'notas' añadida a reservas
-- ✓ Columna 'color' añadida a espacios
-- ✓ Usuarios existentes actualizados como 'profesor'
-- ✓ Índices creados para mejorar rendimiento

-- PRÓXIMOS PASOS:
-- 1. Ejecutar app.py para crear el usuario admin automáticamente
-- 2. Iniciar sesión con: admin / admin123
-- 3. ¡CAMBIAR LA CONTRASEÑA INMEDIATAMENTE!
-- 4. Crear los primeros usuarios profesores desde el panel de admin

-- ====================================================================
