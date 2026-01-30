-- ====================================================================
-- CONSULTAS ÚTILES PARA ADMINISTRACIÓN - SISTEMA DE RESERVAS
-- ====================================================================

-- ====================================================================
-- 1. CONSULTAS DE INFORMACIÓN GENERAL
-- ====================================================================

-- Ver todos los usuarios con sus sedes
SELECT 
    u.id,
    u.username,
    u.email,
    u.rol,
    u.activo,
    u.fecha_creacion,
    STRING_AGG(s.nombre, ', ') as sedes_asignadas
FROM usuarios u
LEFT JOIN usuario_sede us ON u.id = us.usuario_id
LEFT JOIN sedes s ON us.sede_id = s.id
GROUP BY u.id, u.username, u.email, u.rol, u.activo, u.fecha_creacion
ORDER BY u.fecha_creacion DESC;

-- Ver estadísticas generales
SELECT 
    (SELECT COUNT(*) FROM usuarios WHERE activo = TRUE) as usuarios_activos,
    (SELECT COUNT(*) FROM usuarios WHERE rol = 'admin') as administradores,
    (SELECT COUNT(*) FROM usuarios WHERE rol = 'profesor') as profesores,
    (SELECT COUNT(*) FROM reservas) as total_reservas,
    (SELECT COUNT(*) FROM candidatos) as total_candidatos,
    (SELECT COUNT(*) FROM candidatos WHERE estado = 'pendiente') as candidatos_pendientes,
    (SELECT COUNT(*) FROM candidatos WHERE estado = 'asignado') as candidatos_asignados,
    (SELECT COUNT(*) FROM asignaciones) as total_asignaciones;

-- ====================================================================
-- 2. GESTIÓN DE USUARIOS
-- ====================================================================

-- Crear nuevo usuario profesor con sedes
-- Paso 1: Insertar usuario
INSERT INTO usuarios (username, email, password, rol, activo)
VALUES ('nuevo_profesor', 'profesor@ejemplo.com', 'HASH_CONTRASEÑA', 'profesor', TRUE);

-- Paso 2: Asignar sedes (obtener el ID del usuario recién creado)
INSERT INTO usuario_sede (usuario_id, sede_id)
SELECT 
    (SELECT id FROM usuarios WHERE username = 'nuevo_profesor'),
    id 
FROM sedes 
WHERE nombre IN ('Bormujos', 'Ciempozuelos');

-- Activar/Desactivar usuario
UPDATE usuarios SET activo = FALSE WHERE username = 'nombre_usuario';
UPDATE usuarios SET activo = TRUE WHERE username = 'nombre_usuario';

-- Cambiar rol de usuario
UPDATE usuarios SET rol = 'admin' WHERE username = 'nombre_usuario';

-- Resetear contraseña de usuario (generar hash primero con Python)
UPDATE usuarios 
SET password = 'NUEVO_HASH_CONTRASEÑA' 
WHERE username = 'nombre_usuario';

-- Eliminar usuario (cuidado: elimina todas sus reservas y asignaciones)
DELETE FROM usuarios WHERE username = 'nombre_usuario';

-- ====================================================================
-- 3. CONSULTAS DE RESERVAS
-- ====================================================================

-- Ver reservas de una semana específica
SELECT 
    r.id,
    r.fecha,
    TO_CHAR(r.fecha, 'Day') as dia_semana,
    r.hora_inicio,
    r.hora_fin,
    u.username as entrevistador,
    e.nombre as espacio,
    r.prioridad,
    COUNT(a.id) as num_asignaciones,
    STRING_AGG(c.nombre || ' ' || c.apellidos, ', ') as candidatos
FROM reservas r
JOIN usuarios u ON r.usuario_id = u.id
LEFT JOIN espacios e ON r.espacio_id = e.id
LEFT JOIN asignaciones a ON r.id = a.reserva_id
LEFT JOIN candidatos c ON a.candidato_id = c.id
WHERE r.fecha BETWEEN '2025-02-03' AND '2025-02-07'  -- Ajustar fechas
GROUP BY r.id, r.fecha, r.hora_inicio, r.hora_fin, u.username, e.nombre, r.prioridad
ORDER BY r.fecha, r.hora_inicio;

-- Ver reservas con espacios libres
SELECT 
    r.id,
    r.fecha,
    r.hora_inicio,
    u.username as entrevistador,
    COUNT(a.id) as asignaciones_actuales,
    (2 - COUNT(a.id)) as espacios_libres
FROM reservas r
JOIN usuarios u ON r.usuario_id = u.id
LEFT JOIN asignaciones a ON r.id = a.reserva_id
WHERE r.fecha >= CURRENT_DATE
GROUP BY r.id, r.fecha, r.hora_inicio, u.username
HAVING COUNT(a.id) < 2
ORDER BY r.fecha, r.hora_inicio;

-- Eliminar reservas de una fecha específica
DELETE FROM reservas WHERE fecha = '2025-02-10';

-- Eliminar reservas de un usuario específico
DELETE FROM reservas WHERE usuario_id = (SELECT id FROM usuarios WHERE username = 'nombre_usuario');

-- ====================================================================
-- 4. CONSULTAS DE CANDIDATOS
-- ====================================================================

-- Ver candidatos de una semana con su estado
SELECT 
    c.id,
    c.solicitud,
    c.nombre || ' ' || c.apellidos as nombre_completo,
    c.email,
    c.telefono,
    c.media_estudios,
    c.sede,
    c.primera_opcion,
    c.estado,
    c.semana_carga,
    CASE 
        WHEN a.id IS NOT NULL THEN 'Asignado'
        ELSE 'Sin asignar'
    END as tiene_asignacion
FROM candidatos c
LEFT JOIN asignaciones a ON c.id = a.candidato_id
WHERE c.semana_carga = '2025-W06'  -- Ajustar semana
ORDER BY c.media_estudios ASC;

-- Ver candidatos por sede
SELECT 
    sede,
    COUNT(*) as total,
    COUNT(CASE WHEN estado = 'pendiente' THEN 1 END) as pendientes,
    COUNT(CASE WHEN estado = 'asignado' THEN 1 END) as asignados,
    AVG(media_estudios) as nota_media
FROM candidatos
WHERE semana_carga = '2025-W06'  -- Ajustar semana
GROUP BY sede
ORDER BY sede;

-- Candidatos con notas más bajas (prioridad para asignación)
SELECT 
    solicitud,
    nombre || ' ' || apellidos as nombre_completo,
    email,
    media_estudios,
    sede,
    estado
FROM candidatos
WHERE estado = 'pendiente' AND semana_carga = '2025-W06'
ORDER BY media_estudios ASC
LIMIT 20;

-- Eliminar candidatos de una semana específica
DELETE FROM candidatos WHERE semana_carga = '2025-W06';

-- Actualizar sede de candidatos sin sede detectada
UPDATE candidatos
SET sede = 'Bormujos'
WHERE sede IS NULL 
  AND primera_opcion ILIKE '%bormujos%'
  AND semana_carga = '2025-W06';

-- ====================================================================
-- 5. CONSULTAS DE ASIGNACIONES
-- ====================================================================

-- Ver asignaciones completas de una semana
SELECT 
    a.id,
    r.fecha,
    TO_CHAR(r.fecha, 'Day') as dia_semana,
    r.hora_inicio,
    a.posicion,
    c.nombre || ' ' || c.apellidos as candidato,
    c.email as candidato_email,
    c.telefono as candidato_telefono,
    c.media_estudios as candidato_nota,
    c.primera_opcion,
    u.username as entrevistador,
    u.email as entrevistador_email,
    a.estado,
    a.enviado_email,
    a.fecha_asignacion
FROM asignaciones a
JOIN candidatos c ON a.candidato_id = c.id
JOIN reservas r ON a.reserva_id = r.id
JOIN usuarios u ON a.entrevistador_id = u.id
WHERE c.semana_carga = '2025-W06'  -- Ajustar semana
ORDER BY r.fecha, r.hora_inicio, a.posicion;

-- Ver carga de trabajo por entrevistador
SELECT 
    u.username as entrevistador,
    u.email,
    COUNT(a.id) as num_entrevistas,
    STRING_AGG(DISTINCT TO_CHAR(r.fecha, 'DD/MM/YYYY'), ', ') as fechas
FROM usuarios u
LEFT JOIN asignaciones a ON u.id = a.entrevistador_id
LEFT JOIN reservas r ON a.reserva_id = r.id
LEFT JOIN candidatos c ON a.candidato_id = c.id
WHERE c.semana_carga = '2025-W06'  -- Ajustar semana
GROUP BY u.id, u.username, u.email
ORDER BY num_entrevistas DESC;

-- Eliminar todas las asignaciones de una semana (resetea candidatos a pendiente)
UPDATE candidatos 
SET estado = 'pendiente' 
WHERE id IN (
    SELECT candidato_id 
    FROM asignaciones a
    JOIN candidatos c ON a.candidato_id = c.id
    WHERE c.semana_carga = '2025-W06'
);

DELETE FROM asignaciones
WHERE candidato_id IN (
    SELECT id FROM candidatos WHERE semana_carga = '2025-W06'
);

-- ====================================================================
-- 6. CONSULTAS DE LOGS Y AUDITORÍA
-- ====================================================================

-- Ver últimas 50 acciones del sistema
SELECT 
    fecha_hora,
    usuario_username,
    accion,
    entidad,
    descripcion,
    nivel
FROM logs_actividad
ORDER BY fecha_hora DESC
LIMIT 50;

-- Ver acciones de un usuario específico
SELECT 
    fecha_hora,
    accion,
    entidad,
    descripcion
FROM logs_actividad
WHERE usuario_username = 'admin'
ORDER BY fecha_hora DESC;

-- Ver logs de errores
SELECT 
    fecha_hora,
    usuario_username,
    accion,
    entidad,
    descripcion
FROM logs_actividad
WHERE nivel IN ('error', 'critical')
ORDER BY fecha_hora DESC;

-- Limpiar logs antiguos (más de 90 días)
DELETE FROM logs_actividad 
WHERE fecha_hora < CURRENT_DATE - INTERVAL '90 days';

-- ====================================================================
-- 7. MANTENIMIENTO Y LIMPIEZA
-- ====================================================================

-- Ver tamaño de las tablas
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Limpiar candidatos y asignaciones antiguas (más de 6 meses)
DELETE FROM candidatos 
WHERE fecha_carga < CURRENT_DATE - INTERVAL '6 months';

-- Vaciar y reiniciar secuencias de IDs (CUIDADO: ELIMINA TODOS LOS DATOS)
-- TRUNCATE TABLE candidatos RESTART IDENTITY CASCADE;
-- TRUNCATE TABLE asignaciones RESTART IDENTITY CASCADE;
-- TRUNCATE TABLE reservas RESTART IDENTITY CASCADE;

-- Reindexar todas las tablas para optimizar rendimiento
REINDEX DATABASE reservas_db;

-- Actualizar estadísticas de PostgreSQL
ANALYZE;

-- ====================================================================
-- 8. BACKUP Y RESTORE
-- ====================================================================

-- Desde línea de comandos (no ejecutar en psql):

-- Backup completo
-- pg_dump -U postgres -F c -b -v -f backup_reservas.backup reservas_db

-- Backup solo datos
-- pg_dump -U postgres --data-only -f backup_datos.sql reservas_db

-- Backup solo estructura
-- pg_dump -U postgres --schema-only -f backup_estructura.sql reservas_db

-- Restore desde backup
-- pg_restore -U postgres -d reservas_db -v backup_reservas.backup

-- Restore desde SQL
-- psql -U postgres reservas_db < backup_datos.sql

-- ====================================================================
-- 9. CONSULTAS DE DIAGNÓSTICO
-- ====================================================================

-- Ver conexiones activas
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    query
FROM pg_stat_activity
WHERE datname = 'reservas_db';

-- Ver tablas sin índices
SELECT 
    schemaname,
    tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT IN (
      SELECT tablename 
      FROM pg_indexes 
      WHERE schemaname = 'public'
  );

-- Ver índices no utilizados
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname = 'public'
ORDER BY schemaname, tablename, indexname;

-- ====================================================================
-- 10. SEGURIDAD
-- ====================================================================

-- Crear usuario con permisos limitados (solo lectura)
CREATE USER usuario_lectura WITH PASSWORD 'contraseña_segura';
GRANT CONNECT ON DATABASE reservas_db TO usuario_lectura;
GRANT USAGE ON SCHEMA public TO usuario_lectura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO usuario_lectura;

-- Revocar permisos de escritura
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM usuario_lectura;

-- Ver permisos de un usuario
SELECT 
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'usuario_lectura'
ORDER BY table_name, privilege_type;

-- ====================================================================
-- FIN DE CONSULTAS ÚTILES
-- ====================================================================
