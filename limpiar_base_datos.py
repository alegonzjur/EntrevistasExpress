"""
Script para limpiar datos de prueba de la base de datos
Mantiene la estructura de tablas pero elimina todos los datos de:
- Candidatos
- Asignaciones
- Reservas (opcional)
- Logs de asignación
- Logs de carga

IMPORTANTE: NO elimina usuarios ni espacios
"""

from app import app, db
from app import (
    Candidato, Asignacion, Reserva, LogAsignacion, 
    Usuario, Espacio
)
from sqlalchemy import text

def limpiar_base_datos(limpiar_reservas=True, limpiar_logs=True):
    """
    Limpia los datos de prueba de la base de datos
    
    Args:
        limpiar_reservas: Si True, elimina también las reservas
        limpiar_logs: Si True, elimina los logs de asignación y carga
    """
    
    with app.app_context():
        print("\n" + "="*60)
        print("🧹 LIMPIEZA DE BASE DE DATOS")
        print("="*60 + "\n")
        
        try:
            # Contar registros antes
            print("📊 ESTADO ANTES DE LIMPIAR:")
            print("-" * 60)
            candidatos_antes = Candidato.query.count()
            asignaciones_antes = Asignacion.query.count()
            reservas_antes = Reserva.query.count()
            logs_asig_antes = LogAsignacion.query.count()
            usuarios = Usuario.query.count()
            espacios = Espacio.query.count()
            
            print(f"👥 Candidatos:           {candidatos_antes}")
            print(f"📋 Asignaciones:         {asignaciones_antes}")
            print(f"📅 Reservas:             {reservas_antes}")
            print(f"📝 Logs Asignación:      {logs_asig_antes}")
            print(f"🔒 Usuarios (NO tocar):  {usuarios}")
            print(f"🔒 Espacios (NO tocar):  {espacios}")
            print()
            
            # Confirmación
            respuesta = input("⚠️  ¿Estás seguro de que quieres eliminar estos datos? (si/no): ")
            if respuesta.lower() not in ['si', 'sí', 's', 'yes', 'y']:
                print("\n❌ Operación cancelada por el usuario")
                return
            
            print("\n🗑️  Eliminando datos...")
            print("-" * 60)
            
            # 1. Eliminar asignaciones primero (tienen FK a candidatos y reservas)
            if asignaciones_antes > 0:
                Asignacion.query.delete()
                print(f"✅ Asignaciones eliminadas: {asignaciones_antes}")
            
            # 2. Eliminar candidatos
            if candidatos_antes > 0:
                Candidato.query.delete()
                print(f"✅ Candidatos eliminados: {candidatos_antes}")
            
            # 3. Eliminar reservas (opcional)
            if limpiar_reservas and reservas_antes > 0:
                Reserva.query.delete()
                print(f"✅ Reservas eliminadas: {reservas_antes}")
            elif not limpiar_reservas:
                print(f"⏭️  Reservas mantenidas: {reservas_antes}")
            
            # 4. Eliminar logs (opcional)
            if limpiar_logs:
                if logs_asig_antes > 0:
                    LogAsignacion.query.delete()
                    print(f"✅ Logs de asignación eliminados: {logs_asig_antes}")
            else:
                print(f"⏭️  Logs mantenidos")
            
            # Commit de todos los cambios
            db.session.commit()
            
            print()
            print("="*60)
            print("✅ LIMPIEZA COMPLETADA CON ÉXITO")
            print("="*60)
            
            # Verificar que está limpio
            print("\n📊 ESTADO DESPUÉS DE LIMPIAR:")
            print("-" * 60)
            print(f"👥 Candidatos:           {Candidato.query.count()}")
            print(f"📋 Asignaciones:         {Asignacion.query.count()}")
            print(f"📅 Reservas:             {Reserva.query.count()}")
            print(f"📝 Logs Asignación:      {LogAsignacion.query.count()}")
            print(f"✅ Usuarios (intactos):  {Usuario.query.count()}")
            print(f"✅ Espacios (intactos):  {Espacio.query.count()}")
            print()
            
            # Reset de autoincrement (opcional)
            print("🔄 Reseteando contadores de IDs...")
            try:
                # Detectar tipo de base de datos
                engine_name = db.engine.name
                
                if engine_name == 'sqlite':
                    # SQLite
                    db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='candidatos'"))
                    db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='asignaciones'"))
                    if limpiar_reservas:
                        db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='reservas'"))
                    if limpiar_logs:
                        db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='logs_asignacion'"))
                    db.session.commit()
                    print("✅ Contadores reseteados (SQLite)")
                    
                elif engine_name == 'postgresql':
                    # PostgreSQL
                    db.session.execute(text("ALTER SEQUENCE candidatos_id_seq RESTART WITH 1"))
                    db.session.execute(text("ALTER SEQUENCE asignaciones_id_seq RESTART WITH 1"))
                    if limpiar_reservas:
                        db.session.execute(text("ALTER SEQUENCE reservas_id_seq RESTART WITH 1"))
                    if limpiar_logs:
                        db.session.execute(text("ALTER SEQUENCE logs_asignacion_id_seq RESTART WITH 1"))
                    db.session.commit()
                    print("✅ Contadores reseteados (PostgreSQL)")
                    
                elif engine_name == 'mysql':
                    # MySQL
                    db.session.execute(text("ALTER TABLE candidatos AUTO_INCREMENT = 1"))
                    db.session.execute(text("ALTER TABLE asignaciones AUTO_INCREMENT = 1"))
                    if limpiar_reservas:
                        db.session.execute(text("ALTER TABLE reservas AUTO_INCREMENT = 1"))
                    if limpiar_logs:
                        db.session.execute(text("ALTER TABLE logs_asignacion AUTO_INCREMENT = 1"))
                    db.session.commit()
                    print("✅ Contadores reseteados (MySQL)")
                    
                else:
                    print(f"⚠️  Base de datos '{engine_name}' detectada. Reset de contadores omitido.")
                    
            except Exception as e:
                # Si hay error, continuar sin resetear
                print(f"⚠️  No se pudieron resetear contadores: {e}")
                print("   (Los datos se limpiaron correctamente, solo no se resetearon los IDs)")
            
            print("\n" + "="*60)
            print("🎉 BASE DE DATOS LISTA PARA NUEVAS PRUEBAS")
            print("="*60 + "\n")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR al limpiar base de datos: {str(e)}")
            print("La base de datos no ha sido modificada")
            import traceback
            traceback.print_exc()


def limpiar_solo_candidatos():
    """Limpia solo candidatos y asignaciones, mantiene reservas y logs"""
    with app.app_context():
        print("\n🧹 Limpiando solo candidatos y asignaciones...")
        
        asignaciones = Asignacion.query.count()
        candidatos = Candidato.query.count()
        
        if asignaciones > 0:
            Asignacion.query.delete()
            print(f"✅ {asignaciones} asignaciones eliminadas")
        
        if candidatos > 0:
            Candidato.query.delete()
            print(f"✅ {candidatos} candidatos eliminados")
        
        db.session.commit()
        print("✅ Limpieza completada\n")


def limpiar_solo_asignaciones():
    """Limpia solo asignaciones, mantiene candidatos"""
    with app.app_context():
        print("\n🧹 Limpiando solo asignaciones...")
        
        asignaciones = Asignacion.query.count()
        
        if asignaciones > 0:
            Asignacion.query.delete()
            db.session.commit()
            print(f"✅ {asignaciones} asignaciones eliminadas")
        else:
            print("ℹ️  No hay asignaciones para eliminar")
        
        print("✅ Limpieza completada\n")


def mostrar_estado():
    """Muestra el estado actual de la base de datos"""
    with app.app_context():
        print("\n" + "="*60)
        print("📊 ESTADO ACTUAL DE LA BASE DE DATOS")
        print("="*60)
        
        print(f"\n👥 Candidatos:       {Candidato.query.count()}")
        print(f"📋 Asignaciones:     {Asignacion.query.count()}")
        print(f"📅 Reservas:         {Reserva.query.count()}")
        print(f"📝 Logs Asignación:  {LogAsignacion.query.count()}")
        print(f"👤 Usuarios:         {Usuario.query.count()}")
        print(f"🏢 Espacios:         {Espacio.query.count()}")
        print()


if __name__ == '__main__':
    import sys
    
    print("\n" + "="*60)
    print("🧹 SCRIPT DE LIMPIEZA DE BASE DE DATOS")
    print("="*60)
    print("\nOpciones disponibles:")
    print("  1. Limpiar TODO (candidatos, asignaciones, reservas, logs)")
    print("  2. Limpiar candidatos y asignaciones (mantener reservas)")
    print("  3. Limpiar solo asignaciones (mantener candidatos)")
    print("  4. Ver estado actual")
    print("  0. Salir")
    print()
    
    while True:
        try:
            opcion = input("Selecciona una opción (0-4): ").strip()
            
            if opcion == '0':
                print("\n👋 Saliendo...\n")
                break
            
            elif opcion == '1':
                limpiar_base_datos(limpiar_reservas=True, limpiar_logs=True)
                break
            
            elif opcion == '2':
                limpiar_base_datos(limpiar_reservas=False, limpiar_logs=False)
                break
            
            elif opcion == '3':
                limpiar_solo_asignaciones()
                break
            
            elif opcion == '4':
                mostrar_estado()
                continue
            
            else:
                print("❌ Opción inválida. Intenta de nuevo.\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Operación cancelada por el usuario\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            break
