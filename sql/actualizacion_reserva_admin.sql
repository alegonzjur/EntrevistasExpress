-- ====================================================================
-- ACTUALIZACIÓN: RESERVAS CREADAS POR ADMINISTRADORES
-- Sistema de Reservas - Base de datos PostgreSQL
-- ====================================================================
--
-- Este script añade la funcionalidad para que los administradores
-- puedan crear reservas en nombre de otros usuarios (profesores).
--
-- ====================================================================

-- 1. AÑADIR COLUMNA A LA TABLA RESERVAS
-- ====================================================================

-- Columna CREADO_POR_ADMIN: ID del admin que creó la reserva (si aplica)
-- NULL si el usuario creó su propia reserva
ALTER TABLE reservas 
ADD COLUMN IF NOT EXISTS creado_por_admin INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;

-- Crear índice para búsquedas más rápidas
CREATE INDEX IF NOT EXISTS idx_reservas_creado_por_admin 
ON reservas(creado_por_admin);


-- 2. VERIFICACIÓN
-- ====================================================================

-- Verificar que la columna se añadió correctamente
SELECT 
    column_name, 
    data_type, 
    column_default,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'reservas' 
  AND column_name = 'creado_por_admin';


-- 3. CONSULTAS ÚTILES
-- ====================================================================

-- Ver reservas creadas por administradores en nombre de otros
SELECT 
    r.id,
    u_reserva.username AS usuario_reserva,
    u_admin.username AS creado_por_admin,
    e.nombre AS dia,
    r.fecha,
    r.hora_inicio,
    r.hora_fin,
    r.notas
FROM reservas r
JOIN usuarios u_reserva ON r.usuario_id = u_reserva.id
LEFT JOIN usuarios u_admin ON r.creado_por_admin = u_admin.id
JOIN espacios e ON r.espacio_id = e.id
WHERE r.creado_por_admin IS NOT NULL
ORDER BY r.fecha DESC, r.hora_inicio;

-- Contar cuántas reservas ha creado cada administrador para otros
SELECT 
    u.username AS administrador,
    COUNT(r.id) AS reservas_creadas_para_otros
FROM usuarios u
LEFT JOIN reservas r ON u.id = r.creado_por_admin
WHERE u.rol = 'admin'
GROUP BY u.username
ORDER BY reservas_creadas_para_otros DESC;

-- Ver todas las reservas de un usuario, indicando quién las creó
SELECT 
    r.id,
    r.fecha,
    r.hora_inicio,
    r.hora_fin,
    e.nombre AS dia,
    CASE 
        WHEN r.creado_por_admin IS NULL THEN 'Por el propio usuario'
        ELSE CONCAT('Por admin: ', u_admin.username)
    END AS creada_por,
    r.notas
FROM reservas r
JOIN espacios e ON r.espacio_id = e.id
LEFT JOIN usuarios u_admin ON r.creado_por_admin = u_admin.id
WHERE r.usuario_id = 1  -- Cambiar el ID por el usuario que quieras ver
ORDER BY r.fecha, r.hora_inicio;


-- ====================================================================
-- FIN DEL SCRIPT
-- ====================================================================

-- RESUMEN DE CAMBIOS:
-- ✓ Columna 'creado_por_admin' añadida a la tabla reservas
-- ✓ Índice creado para mejorar rendimiento
-- ✓ Los administradores ahora pueden crear reservas para otros usuarios

-- PRÓXIMOS PASOS:
-- 1. Reiniciar la aplicación con el nuevo app.py
-- 2. Los administradores verán un selector de usuario en la página de reservas
-- 3. Podrán elegir para quién reservar antes de seleccionar una franja

-- ====================================================================
