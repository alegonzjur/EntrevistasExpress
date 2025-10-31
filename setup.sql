-- Crear la base de datos
CREATE DATABASE reservas_db;

-- Conectarse a la base de datos
\c reservas_db

-- Crear usuario (opcional, si no existe)
CREATE USER usuario WITH PASSWORD 'password';

-- Dar permisos al usuario
GRANT ALL PRIVILEGES ON DATABASE reservas_db TO usuario;
GRANT ALL ON SCHEMA public TO usuario;

-- Las tablas se crearán automáticamente con SQLAlchemy
-- cuando ejecutes la aplicación por primera vez