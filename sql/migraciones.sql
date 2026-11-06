-- ====================================================================
-- REGISTRO DE MIGRACIONES DE ESQUEMA — EntrevistasExpress
-- ====================================================================
--
-- Qué es este fichero:
-- Un registro manual, en orden cronológico, de cada cambio de esquema
-- real que se aplique a la base de datos de producción a partir de la
-- reconstrucción de octubre de 2026 (modelos en app/models/, esquema de
-- referencia inicial en sql/esquema.sql).
--
-- No es lo mismo que sql/esquema.sql: ese fichero es una foto fija del
-- esquema completo en un momento dado (se regenera entero); este fichero
-- es un historial incremental — cada entrada es el ALTER/CREATE/DROP
-- exacto que hay que ejecutar a mano en el PostgreSQL real para que su
-- esquema pase de la versión N a la versión N+1. Útil porque
-- db.create_all() (ver app/seed.py) crea tablas que no existen, pero NO
-- modifica columnas de una tabla que ya existe — así que un cambio en un
-- modelo (añadir una columna, cambiar un tipo, etc.) no se aplica solo
-- con reiniciar la app; hay que aplicarlo aquí, a mano, contra la BD real.
--
-- Convención para cada entrada nueva:
--   1. Encabezado con fecha (AAAA-MM-DD) y una frase de qué cambia y por
--      qué, en el mismo estilo que el resto del proyecto (explicar antes
--      de ejecutar).
--   2. El SQL exacto a ejecutar, en el orden en que debe aplicarse.
--   3. Si el cambio tiene vuelta atrás razonable, un bloque "-- Rollback:"
--      con el SQL para deshacerlo.
--
-- Al aplicar una entrada en el PostgreSQL real, márcala aquí como
-- aplicada (añade "-- ✅ Aplicado en <entorno> el <fecha>" bajo su
-- encabezado) para que el registro refleje el estado real, no solo la
-- intención.
--
-- ====================================================================

-- [2026-10-15] Nuevos campos de candidato capturados del Excel semanal:
-- forma_acceso, tipo_bachillerato, tipo_fpii_cgs y convocatoria (para
-- mostrar más información en el botón de acciones, a configurar en un
-- paso posterior). tipo_bachillerato y tipo_fpii_cgs llevan DEFAULT
-- 'No disponible' porque así los pide negocio cuando el Excel los trae
-- vacíos; las filas ya existentes en la tabla (candidatos cargados
-- antes de esta migración) pasan a tener ese mismo valor por defecto,
-- en vez de quedar en NULL, para no mezclar dos significados distintos
-- de "vacío" en la misma columna.
-- ✅ Aplicado en: (pendiente)

ALTER TABLE candidatos ADD COLUMN forma_acceso VARCHAR(50);
ALTER TABLE candidatos ADD COLUMN tipo_bachillerato VARCHAR(100) DEFAULT 'No disponible';
ALTER TABLE candidatos ADD COLUMN tipo_fpii_cgs VARCHAR(100) DEFAULT 'No disponible';
ALTER TABLE candidatos ADD COLUMN convocatoria INTEGER;

UPDATE candidatos SET tipo_bachillerato = 'No disponible' WHERE tipo_bachillerato IS NULL;
UPDATE candidatos SET tipo_fpii_cgs = 'No disponible' WHERE tipo_fpii_cgs IS NULL;

-- Rollback:
-- ALTER TABLE candidatos DROP COLUMN forma_acceso;
-- ALTER TABLE candidatos DROP COLUMN tipo_bachillerato;
-- ALTER TABLE candidatos DROP COLUMN tipo_fpii_cgs;
-- ALTER TABLE candidatos DROP COLUMN convocatoria;

-- ====================================================================

-- [2026-10-15] media_estudios deja de ser obligatoria: un candidato debe
-- poder cargarse aunque el Excel semanal traiga esa celda vacía para él.
-- A partir de ahora, sin nota se muestra como "No disponible" en vez de
-- bloquear la carga (ver Candidato.media_estudios_texto en el modelo, y
-- services/etl_candidatos.py). No se toca ningún dato existente: los
-- candidatos ya cargados conservan su nota real.
-- ✅ Aplicado en: (pendiente)

ALTER TABLE candidatos ALTER COLUMN media_estudios DROP NOT NULL;

-- Rollback (solo es seguro si, para entonces, ningún candidato tiene
-- media_estudios NULL; si lo tiene, decide primero qué nota ponerle):
-- ALTER TABLE candidatos ALTER COLUMN media_estudios SET NOT NULL;

-- [2026-11-05] Días bloqueados por campus: festivos locales u otros días en
-- los que no se asignan entrevistas a los candidatos de un campus. La
-- asignación automática ignora cada pareja fecha + sede (ver
-- services/asignacion.py y models/dia_bloqueado.py). Tabla nueva: no se
-- toca ningún dato existente.
-- ✅ Aplicado en: (pendiente)

CREATE TABLE IF NOT EXISTS dias_bloqueados (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    sede VARCHAR(50) NOT NULL,
    motivo VARCHAR(255),
    creado_por_usuario_id INTEGER REFERENCES usuarios(id),
    fecha_creacion TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_dia_bloqueado_fecha_sede UNIQUE (fecha, sede)
);
CREATE INDEX IF NOT EXISTS ix_dias_bloqueados_fecha ON dias_bloqueados (fecha);

-- Rollback:
-- DROP TABLE dias_bloqueados;

-- ====================================================================
-- Plantilla para la siguiente entrada (bórrala y sustitúyela cuando
-- añadas la próxima migración real):
-- ====================================================================
--
-- -- [AAAA-MM-DD] <Descripción breve del cambio y motivo>
-- -- ✅ Aplicado en: (pendiente)
--
-- ALTER TABLE ...
--
-- -- Rollback:
-- -- ALTER TABLE ...