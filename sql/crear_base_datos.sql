-- ====================================================================
-- SCRIPT DE CREACIÓN DE BASE DE DATOS - SISTEMA DE RESERVAS
-- Base de datos: PostgreSQL
-- Generado desde: app.py
-- ====================================================================

-- ====================================================================
-- PASO 1: CREAR BASE DE DATOS (ejecutar como superusuario postgres)
-- ====================================================================

-- Conectarse como usuario postgres y crear la base de datos
-- psql -U postgres
-- CREATE DATABASE reservas_db;
-- \c reservas_db

-- O ejecutar desde línea de comandos:
-- createdb -U postgres reservas_db

-- ====================================================================
-- PASO 2: ELIMINAR TABLAS EXISTENTES (si es necesario reiniciar)
-- ====================================================================

-- DESCOMENTA ESTAS LÍNEAS SI QUIERES REINICIAR LA BASE DE DATOS
-- DROP TABLE IF EXISTS logs_actividad CASCADE;
-- DROP TABLE IF EXISTS logs_asignacion CASCADE;
-- DROP TABLE IF EXISTS cargas_excel CASCADE;
-- DROP TABLE IF EXISTS asignaciones CASCADE;
-- DROP TABLE IF EXISTS candidatos CASCADE;
-- DROP TABLE IF EXISTS reservas CASCADE;
-- DROP TABLE IF EXISTS usuario_sede CASCADE;
-- DROP TABLE IF EXISTS usuarios CASCADE;
-- DROP TABLE IF EXISTS sedes CASCADE;
-- DROP TABLE IF EXISTS espacios CASCADE;

-- ====================================================================
-- PASO 3: CREAR TABLAS
-- ====================================================================

-- Tabla: sedes
-- Almacena las sedes/campus disponibles
CREATE TABLE IF NOT EXISTS sedes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL,
    activa BOOLEAN DEFAULT TRUE,
    descripcion VARCHAR(255),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla: usuarios
-- Almacena profesores y administradores
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    rol VARCHAR(20) DEFAULT 'profesor' CHECK (rol IN ('admin', 'profesor')),
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enlace_videollamada_personal VARCHAR(500),
    sede VARCHAR(50)  -- Sede principal (legacy, se usa usuario_sede ahora)
);

-- Tabla intermedia: usuario_sede (relación muchos a muchos)
-- Relaciona usuarios con múltiples sedes
CREATE TABLE IF NOT EXISTS usuario_sede (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    sede_id INTEGER NOT NULL REFERENCES sedes(id) ON DELETE CASCADE,
    fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, sede_id)
);

-- Tabla: espacios
-- Representa los días de la semana (Lunes, Martes, etc.)
CREATE TABLE IF NOT EXISTS espacios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    color VARCHAR(7) DEFAULT '#667eea'
);

-- Tabla: reservas
-- Almacena las franjas horarias reservadas por los profesores
CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    espacio_id INTEGER NOT NULL REFERENCES espacios(id) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notas TEXT,
    creado_por_admin INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    prioridad VARCHAR(20) DEFAULT 'normal' CHECK (prioridad IN ('normal', 'secundaria'))
);

-- Tabla: candidatos
-- Almacena los candidatos cargados desde Excel
CREATE TABLE IF NOT EXISTS candidatos (
    id SERIAL PRIMARY KEY,
    solicitud INTEGER NOT NULL,
    apellidos VARCHAR(150) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(120),
    telefono VARCHAR(20),
    media_estudios NUMERIC(4, 2) NOT NULL,
    primera_opcion TEXT,
    sede VARCHAR(50),
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'asignado', 'entrevistado', 'cancelado')),
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    semana_carga VARCHAR(20),
    archivo_origen VARCHAR(255)
);

-- Tabla: asignaciones
-- Relaciona candidatos con reservas (entrevistas programadas)
CREATE TABLE IF NOT EXISTS asignaciones (
    id SERIAL PRIMARY KEY,
    candidato_id INTEGER NOT NULL UNIQUE REFERENCES candidatos(id) ON DELETE CASCADE,
    reserva_id INTEGER NOT NULL REFERENCES reservas(id) ON DELETE CASCADE,
    entrevistador_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    posicion SMALLINT NOT NULL CHECK (posicion IN (1, 2)),
    minuto_inicio SMALLINT NOT NULL,
    estado VARCHAR(20) DEFAULT 'confirmado' CHECK (estado IN ('confirmado', 'cancelado', 'completado')),
    enviado_email BOOLEAN DEFAULT FALSE,
    fecha_email TIMESTAMP,
    resultado TEXT,
    notas_entrevista TEXT,
    fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    asignado_por_admin_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Tabla: logs_asignacion
-- Registra ejecuciones del algoritmo de asignación automática
CREATE TABLE IF NOT EXISTS logs_asignacion (
    id SERIAL PRIMARY KEY,
    fecha_ejecucion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    semana_objetivo VARCHAR(20) NOT NULL,
    candidatos_procesados INTEGER NOT NULL,
    candidatos_filtrados INTEGER NOT NULL,
    candidatos_asignados INTEGER NOT NULL,
    candidatos_sin_asignar INTEGER NOT NULL,
    franjas_utilizadas INTEGER NOT NULL,
    algoritmo_usado VARCHAR(50) DEFAULT 'balanceado',
    tiempo_ejecucion_segundos NUMERIC(6, 2),
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('exito', 'parcial', 'error')),
    mensaje TEXT,
    ejecutado_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    archivo_origen VARCHAR(255)
);

-- Tabla: cargas_excel
-- Registra las cargas de archivos Excel de candidatos
CREATE TABLE IF NOT EXISTS cargas_excel (
    id SERIAL PRIMARY KEY,
    archivo_nombre VARCHAR(255) NOT NULL,
    archivo_hash VARCHAR(64),
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    candidatos_totales INTEGER NOT NULL,
    candidatos_importados INTEGER NOT NULL,
    candidatos_duplicados INTEGER DEFAULT 0,
    cargado_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    semana_destino VARCHAR(20),
    estado VARCHAR(20) DEFAULT 'completado' CHECK (estado IN ('completado', 'error', 'parcial')),
    mensaje TEXT
);

-- Tabla: logs_actividad
-- Sistema de auditoría completo
CREATE TABLE IF NOT EXISTS logs_actividad (
    id SERIAL PRIMARY KEY,
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_username VARCHAR(80),
    accion VARCHAR(50) NOT NULL,
    entidad VARCHAR(50) NOT NULL,
    entidad_id INTEGER,
    descripcion TEXT NOT NULL,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    ip_address VARCHAR(50),
    user_agent VARCHAR(255),
    nivel VARCHAR(20) DEFAULT 'info' CHECK (nivel IN ('info', 'warning', 'error', 'critical')),
    metadata_extra TEXT
);

-- ====================================================================
-- PASO 4: CREAR ÍNDICES PARA MEJORAR RENDIMIENTO
-- ====================================================================

-- Índices en usuarios
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios(rol);
CREATE INDEX IF NOT EXISTS idx_usuarios_activo ON usuarios(activo);

-- Índices en reservas
CREATE INDEX IF NOT EXISTS idx_reservas_usuario ON reservas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_reservas_fecha ON reservas(fecha);
CREATE INDEX IF NOT EXISTS idx_reservas_espacio ON reservas(espacio_id);
CREATE INDEX IF NOT EXISTS idx_reservas_fecha_hora ON reservas(fecha, hora_inicio);

-- Índices en candidatos
CREATE INDEX IF NOT EXISTS idx_candidatos_solicitud ON candidatos(solicitud);
CREATE INDEX IF NOT EXISTS idx_candidatos_estado ON candidatos(estado);
CREATE INDEX IF NOT EXISTS idx_candidatos_semana ON candidatos(semana_carga);
CREATE INDEX IF NOT EXISTS idx_candidatos_media ON candidatos(media_estudios);
CREATE INDEX IF NOT EXISTS idx_candidatos_sede ON candidatos(sede);

-- Índices en asignaciones
CREATE INDEX IF NOT EXISTS idx_asignaciones_candidato ON asignaciones(candidato_id);
CREATE INDEX IF NOT EXISTS idx_asignaciones_reserva ON asignaciones(reserva_id);
CREATE INDEX IF NOT EXISTS idx_asignaciones_entrevistador ON asignaciones(entrevistador_id);
CREATE INDEX IF NOT EXISTS idx_asignaciones_estado ON asignaciones(estado);

-- Índices en logs_actividad (auditoría)
CREATE INDEX IF NOT EXISTS idx_logs_fecha ON logs_actividad(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_logs_usuario ON logs_actividad(usuario_id);
CREATE INDEX IF NOT EXISTS idx_logs_accion ON logs_actividad(accion);
CREATE INDEX IF NOT EXISTS idx_logs_entidad ON logs_actividad(entidad);
CREATE INDEX IF NOT EXISTS idx_logs_nivel ON logs_actividad(nivel);

-- Índices en cargas_excel
CREATE INDEX IF NOT EXISTS idx_cargas_fecha ON cargas_excel(fecha_carga);
CREATE INDEX IF NOT EXISTS idx_cargas_hash ON cargas_excel(archivo_hash);
CREATE INDEX IF NOT EXISTS idx_cargas_semana ON cargas_excel(semana_destino);

-- ====================================================================
-- PASO 5: INSERTAR DATOS INICIALES
-- ====================================================================

-- Insertar sedes por defecto
INSERT INTO sedes (nombre, activa, descripcion) VALUES
    ('Bormujos', TRUE, 'Campus de Bormujos'),
    ('Ciempozuelos', TRUE, 'Campus de Ciempozuelos'),
    ('Pº de la Habana', TRUE, 'Campus Paseo de la Habana')
ON CONFLICT (nombre) DO NOTHING;

-- Insertar espacios (días de la semana)
INSERT INTO espacios (nombre, descripcion, color) VALUES
    ('Lunes', 'Primer día de la semana', '#667eea'),
    ('Martes', 'Segundo día de la semana', '#764ba2'),
    ('Miércoles', 'Tercer día de la semana', '#f093fb'),
    ('Jueves', 'Cuarto día de la semana', '#4facfe'),
    ('Viernes', 'Quinto día de la semana', '#43e97b')
ON CONFLICT DO NOTHING;

-- Insertar usuario administrador por defecto
-- Contraseña: admin123 (hash generado con werkzeug.security)
-- IMPORTANTE: Cambiar esta contraseña después del primer login
INSERT INTO usuarios (username, email, password, rol, activo) VALUES
    ('admin', 
     'admin@ejemplo.com', 
     'scrypt:32768:8:1$mJqZkLx7KH9qN3Qj$c8e5ed0c9e8d7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2',
     'admin', 
     TRUE)
ON CONFLICT (username) DO NOTHING;

-- NOTA: El hash de arriba es solo un ejemplo. El script init_db.py generará el hash correcto.
-- Si ejecutas este SQL manualmente, debes generar el hash con:
-- python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('admin123'))"

-- ====================================================================
-- PASO 6: VERIFICAR LA INSTALACIÓN
-- ====================================================================

-- Verificar que las tablas se crearon correctamente
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

-- Contar registros en cada tabla
SELECT 'sedes' as tabla, COUNT(*) as registros FROM sedes
UNION ALL
SELECT 'espacios', COUNT(*) FROM espacios
UNION ALL
SELECT 'usuarios', COUNT(*) FROM usuarios
UNION ALL
SELECT 'reservas', COUNT(*) FROM reservas
UNION ALL
SELECT 'candidatos', COUNT(*) FROM candidatos
UNION ALL
SELECT 'asignaciones', COUNT(*) FROM asignaciones
UNION ALL
SELECT 'logs_actividad', COUNT(*) FROM logs_actividad
UNION ALL
SELECT 'cargas_excel', COUNT(*) FROM cargas_excel
UNION ALL
SELECT 'logs_asignacion', COUNT(*) FROM logs_asignacion;

-- Verificar índices creados
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ====================================================================
-- NOTAS IMPORTANTES
-- ====================================================================

-- 1. CONTRASEÑA ADMIN:
--    Usuario: admin
--    Contraseña: admin123
--    ⚠️ CAMBIAR INMEDIATAMENTE después del primer login

-- 2. CONFIGURACIÓN DE CONEXIÓN:
--    En app.py o config.py ajustar:
--    postgresql://usuario:contraseña@localhost/reservas_db

-- 3. PERMISOS:
--    Asegúrate de que el usuario de PostgreSQL tenga permisos:
--    GRANT ALL PRIVILEGES ON DATABASE reservas_db TO tu_usuario;
--    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tu_usuario;
--    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tu_usuario;

-- 4. BACKUP:
--    Para hacer backup de la base de datos:
--    pg_dump -U postgres reservas_db > backup_reservas.sql
--
--    Para restaurar:
--    psql -U postgres reservas_db < backup_reservas.sql

-- 5. MIGRACIONES:
--    Este script crea la estructura inicial.
--    Para cambios futuros, usa Flask-Migrate:
--    python manage.py db migrate -m "descripción del cambio"
--    python manage.py db upgrade

-- ====================================================================
-- FIN DEL SCRIPT
-- ====================================================================

-- Mensaje de confirmación
SELECT 'Base de datos creada correctamente. Recuerda cambiar la contraseña del admin.' AS mensaje;
