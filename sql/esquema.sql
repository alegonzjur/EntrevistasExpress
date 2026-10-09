-- ============================================================================
-- ESQUEMA DE BASE DE DATOS - EntrevistasExpress
-- PostgreSQL. Generado a partir de los modelos SQLAlchemy de app.py.
--
-- Este script SOLO crea la estructura (tablas, claves, índices).
-- No inserta datos: el usuario administrador y los 5 días de la semana
-- los crea la propia aplicación la primera vez que arranca.
--
-- Uso (ejecutar como superusuario postgres):
--   createdb -U postgres entrevistas_db
--   psql -U postgres -d entrevistas_db -f esquema.sql
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Tabla: candidatos
-- Candidatos cargados desde Excel para una semana concreta
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidatos (
	clave_academica VARCHAR(20) NOT NULL, 
	solicitud INTEGER NOT NULL, 
	apellidos VARCHAR(150) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	email VARCHAR(120), 
	telefono VARCHAR(20), 
	media_estudios NUMERIC(4, 2) NOT NULL, 
	primera_opcion TEXT, 
	sede VARCHAR(50), 
	estado VARCHAR(20) NOT NULL, 
	fecha_carga TIMESTAMP WITHOUT TIME ZONE, 
	semana_carga VARCHAR(20), 
	archivo_origen VARCHAR(255), 
	franjas_disponibilidad TEXT, 
	franjas_parseadas TEXT, 
	tiene_preferencias BOOLEAN, 
	PRIMARY KEY (clave_academica)
);

-- ----------------------------------------------------------------------------
-- Tabla: espacios
-- Días de la semana en los que se puede reservar (Lunes..Viernes)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS espacios (
	id SERIAL NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	descripcion TEXT, 
	color VARCHAR(7), 
	PRIMARY KEY (id)
);

-- ----------------------------------------------------------------------------
-- Tabla: sedes
-- Sedes/campus disponibles (Bormujos, Ciempozuelos, etc.)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sedes (
	id SERIAL NOT NULL, 
	nombre VARCHAR(50) NOT NULL, 
	activa BOOLEAN, 
	descripcion VARCHAR(255), 
	fecha_creacion TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

-- ----------------------------------------------------------------------------
-- Tabla: usuarios
-- Profesores y administradores
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
	id SERIAL NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	nombre_completo VARCHAR(150), 
	password VARCHAR(255) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	rol VARCHAR(20), 
	activo BOOLEAN, 
	fecha_creacion TIMESTAMP WITHOUT TIME ZONE, 
	enlace_videollamada_personal VARCHAR(500), 
	sede VARCHAR(50), 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (email)
);

-- ----------------------------------------------------------------------------
-- Tabla: cargas_excel
-- Historial de ficheros Excel de candidatos cargados
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cargas_excel (
	id SERIAL NOT NULL, 
	archivo_nombre VARCHAR(255) NOT NULL, 
	archivo_hash VARCHAR(64), 
	fecha_carga TIMESTAMP WITHOUT TIME ZONE, 
	candidatos_totales INTEGER NOT NULL, 
	candidatos_importados INTEGER NOT NULL, 
	candidatos_duplicados INTEGER, 
	cargado_por_usuario_id INTEGER, 
	semana_destino VARCHAR(20), 
	estado VARCHAR(20), 
	mensaje TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cargado_por_usuario_id) REFERENCES usuarios (id)
);

-- ----------------------------------------------------------------------------
-- Tabla: logs_actividad
-- Auditoría general de acciones realizadas en la aplicación
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_actividad (
	id SERIAL NOT NULL, 
	fecha_hora TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	usuario_id INTEGER, 
	usuario_username VARCHAR(80), 
	accion VARCHAR(50) NOT NULL, 
	entidad VARCHAR(50) NOT NULL, 
	entidad_id INTEGER, 
	descripcion TEXT NOT NULL, 
	datos_anteriores TEXT, 
	datos_nuevos TEXT, 
	ip_address VARCHAR(50), 
	user_agent VARCHAR(255), 
	nivel VARCHAR(20) NOT NULL, 
	metadata_extra TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
);
CREATE INDEX IF NOT EXISTS ix_logs_actividad_entidad ON logs_actividad (entidad);
CREATE INDEX IF NOT EXISTS ix_logs_actividad_accion ON logs_actividad (accion);
CREATE INDEX IF NOT EXISTS ix_logs_actividad_fecha_hora ON logs_actividad (fecha_hora);

-- ----------------------------------------------------------------------------
-- Tabla: logs_asignacion
-- Historial de ejecuciones del algoritmo de asignación automática
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_asignacion (
	id SERIAL NOT NULL, 
	fecha_ejecucion TIMESTAMP WITHOUT TIME ZONE, 
	semana_objetivo VARCHAR(20) NOT NULL, 
	candidatos_procesados INTEGER NOT NULL, 
	candidatos_filtrados INTEGER NOT NULL, 
	candidatos_asignados INTEGER NOT NULL, 
	candidatos_sin_asignar INTEGER NOT NULL, 
	franjas_utilizadas INTEGER NOT NULL, 
	algoritmo_usado VARCHAR(50), 
	tiempo_ejecucion_segundos NUMERIC(6, 2), 
	estado VARCHAR(20) NOT NULL, 
	mensaje TEXT, 
	ejecutado_por_usuario_id INTEGER, 
	archivo_origen VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(ejecutado_por_usuario_id) REFERENCES usuarios (id)
);

-- ----------------------------------------------------------------------------
-- Tabla: reservas
-- Franjas horarias reservadas por un profesor en un espacio/día
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservas (
	id SERIAL NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	espacio_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	hora_inicio TIME WITHOUT TIME ZONE NOT NULL, 
	hora_fin TIME WITHOUT TIME ZONE NOT NULL, 
	fecha_creacion TIMESTAMP WITHOUT TIME ZONE, 
	notas TEXT, 
	creado_por_admin INTEGER, 
	prioridad VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(espacio_id) REFERENCES espacios (id), 
	FOREIGN KEY(creado_por_admin) REFERENCES usuarios (id)
);

-- ----------------------------------------------------------------------------
-- Tabla: usuario_sede
-- Relación N:M entre usuarios y sedes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario_sede (
	usuario_id INTEGER NOT NULL, 
	sede_id INTEGER NOT NULL, 
	fecha_asignacion TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (usuario_id, sede_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
	FOREIGN KEY(sede_id) REFERENCES sedes (id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Tabla: asignaciones
-- Asignación de un candidato a una reserva (franja) concreta
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asignaciones (
	id SERIAL NOT NULL, 
	candidato_clave VARCHAR(20) NOT NULL, 
	reserva_id INTEGER NOT NULL, 
	entrevistador_id INTEGER NOT NULL, 
	posicion SMALLINT NOT NULL, 
	minuto_inicio SMALLINT NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	enviado_email BOOLEAN, 
	fecha_email TIMESTAMP WITHOUT TIME ZONE, 
	resultado TEXT, 
	notas_entrevista TEXT, 
	fecha_asignacion TIMESTAMP WITHOUT TIME ZONE, 
	asignado_por_admin_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (candidato_clave), 
	FOREIGN KEY(candidato_clave) REFERENCES candidatos (clave_academica) ON DELETE CASCADE, 
	FOREIGN KEY(reserva_id) REFERENCES reservas (id) ON DELETE CASCADE, 
	FOREIGN KEY(entrevistador_id) REFERENCES usuarios (id), 
	FOREIGN KEY(asignado_por_admin_id) REFERENCES usuarios (id)
);
