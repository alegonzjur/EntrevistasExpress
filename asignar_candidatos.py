#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Algoritmo de Asignación Automática de Candidatos
Sistema de Reservas - Fundación San Juan de Dios

Este script:
1. Obtiene candidatos pendientes de una semana
2. Busca franjas reservadas disponibles
3. Asigna 2 candidatos por franja (15 minutos cada uno)
4. Balancea la carga entre entrevistadores
5. Prioriza candidatos con menor nota
6. Genera las asignaciones en la BD
7. Registra todo en logs_asignacion

Uso:
    python asignar_candidatos.py --semana 2024-W46
    python asignar_candidatos.py --semana 2024-W46 --auto
    python asignar_candidatos.py --semana 2024-W46 --max-por-profesor 10
"""

import sys
from datetime import datetime, timedelta, time
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import time as time_module

# ====================================================================
# CONFIGURACIÓN
# ====================================================================

DATABASE_URI = 'postgresql://postgres:eebormujos?@localhost/reservas_db'

CONFIG = {
    'max_candidatos_por_franja': 2,      # 2 candidatos por franja de 30 min
    'minutos_por_entrevista': 15,        # 15 minutos por candidato
    'max_por_profesor_default': 999,     # Sin límite por defecto
    'balance_tolerance': 0.2             # Tolerancia 20% para balanceo
}

# ====================================================================
# IMPORTAR MODELOS
# ====================================================================

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date, Time, DateTime, Boolean, Text, Numeric, SmallInteger, ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False)
    rol = Column(String(20))

class Espacio(Base):
    __tablename__ = 'espacios'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)

class Reserva(Base):
    __tablename__ = 'reservas'
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    espacio_id = Column(Integer, ForeignKey('espacios.id'), nullable=False)
    fecha = Column(Date, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    notas = Column(Text)
    
    usuario = relationship('Usuario')
    espacio = relationship('Espacio')
    asignaciones = relationship('Asignacion', back_populates='reserva')

class Candidato(Base):
    __tablename__ = 'candidatos'
    id = Column(Integer, primary_key=True)
    solicitud = Column(Integer, nullable=False)
    apellidos = Column(String(150), nullable=False)
    nombre = Column(String(100), nullable=False)
    email = Column(String(120))
    media_estudios = Column(Numeric(4, 2), nullable=False)
    primera_opcion = Column(Text)
    estado = Column(String(20), default='pendiente', nullable=False)
    fecha_carga = Column(DateTime, default=datetime.utcnow)
    semana_carga = Column(String(20))
    archivo_origen = Column(String(255))
    
    asignacion = relationship('Asignacion', back_populates='candidato', uselist=False)

class Asignacion(Base):
    __tablename__ = 'asignaciones'
    id = Column(Integer, primary_key=True)
    candidato_id = Column(Integer, ForeignKey('candidatos.id', ondelete='CASCADE'), nullable=False, unique=True)
    reserva_id = Column(Integer, ForeignKey('reservas.id', ondelete='CASCADE'), nullable=False)
    entrevistador_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    posicion = Column(SmallInteger, nullable=False)
    minuto_inicio = Column(SmallInteger, nullable=False)
    estado = Column(String(20), default='confirmado', nullable=False)
    enviado_email = Column(Boolean, default=False)
    fecha_email = Column(DateTime)
    resultado = Column(Text)
    notas_entrevista = Column(Text)
    fecha_asignacion = Column(DateTime, default=datetime.utcnow)
    asignado_por_admin_id = Column(Integer, ForeignKey('usuarios.id'))
    
    candidato = relationship('Candidato', back_populates='asignacion')
    reserva = relationship('Reserva', back_populates='asignaciones')
    entrevistador = relationship('Usuario', foreign_keys=[entrevistador_id])

class LogAsignacion(Base):
    __tablename__ = 'logs_asignacion'
    id = Column(Integer, primary_key=True)
    fecha_ejecucion = Column(DateTime, default=datetime.utcnow)
    semana_objetivo = Column(String(20), nullable=False)
    candidatos_procesados = Column(Integer, nullable=False)
    candidatos_filtrados = Column(Integer, nullable=False)
    candidatos_asignados = Column(Integer, nullable=False)
    candidatos_sin_asignar = Column(Integer, nullable=False)
    franjas_utilizadas = Column(Integer, nullable=False)
    algoritmo_usado = Column(String(50), default='balanceado')
    tiempo_ejecucion_segundos = Column(Numeric(6, 2))
    estado = Column(String(20), nullable=False)
    mensaje = Column(Text)
    ejecutado_por_usuario_id = Column(Integer, ForeignKey('usuarios.id'))
    archivo_origen = Column(String(255))

# ====================================================================
# CLASE PRINCIPAL
# ====================================================================

class AsignadorCandidatos:
    """Asigna candidatos a franjas reservadas de forma automática"""
    
    def __init__(self, semana_carga, max_por_profesor=None, admin_user_id=1):
        """
        Inicializa el asignador
        
        Args:
            semana_carga (str): Semana de carga de candidatos en formato '2024-W45'
            max_por_profesor (int): Máximo de candidatos por profesor
            admin_user_id (int): ID del usuario admin que ejecuta (default: 1)
        """
        self.semana_carga = semana_carga
        self.semana_entrevistas = self._calcular_semana_siguiente(semana_carga)
        self.max_por_profesor = max_por_profesor or CONFIG['max_por_profesor_default']
        self.admin_user_id = admin_user_id
        
        # Crear sesión de BD
        engine = create_engine(DATABASE_URI, connect_args={'client_encoding': 'utf8'})
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
        # Variables de estado
        self.candidatos_pendientes = []
        self.franjas_disponibles = []
        self.asignaciones_creadas = []
        self.estadisticas = {
            'inicio': datetime.now(),
            'candidatos_procesados': 0,
            'candidatos_filtrados': 0,
            'candidatos_asignados': 0,
            'candidatos_sin_asignar': 0,
            'franjas_utilizadas': 0
        }
        
        print(f"🎯 Asignador de Candidatos")
        print(f"📥 Semana de carga (candidatos): {semana_carga}")
        print(f"📅 Semana de entrevistas (reservas): {self.semana_entrevistas}")
        print(f"📊 Máximo por profesor: {self.max_por_profesor}")
        print("=" * 70)
    
    def _calcular_semana_siguiente(self, semana_iso):
        """
        Calcula la semana siguiente en formato ISO
        
        Args:
            semana_iso (str): Semana en formato '2024-W45'
        
        Returns:
            str: Semana siguiente en formato '2024-W46'
        """
        # Parsear semana formato ISO (2024-W45)
        año, semana_num = semana_iso.split('-W')
        año = int(año)
        semana_num = int(semana_num)
        
        # Calcular primer día de la semana
        primer_dia = datetime.strptime(f'{año}-W{semana_num:02d}-1', '%Y-W%W-%w').date()
        
        # Sumar 7 días para siguiente semana
        siguiente_lunes = primer_dia + timedelta(days=7)
        
        # Formatear de vuelta a ISO
        semana_siguiente = siguiente_lunes.strftime('%Y-W%W')
        
        return semana_siguiente
    
    def obtener_rango_fechas_semana(self):
        """Calcula el rango de fechas (lunes a viernes) de la semana de entrevistas"""
        # Parsear semana formato ISO (2024-W46)
        año, semana_num = self.semana_entrevistas.split('-W')
        año = int(año)
        semana_num = int(semana_num)
        
        # Calcular primer día de la semana (lunes)
        primer_dia = datetime.strptime(f'{año}-W{semana_num:02d}-1', '%Y-W%W-%w').date()
        
        # Lunes a Viernes
        lunes = primer_dia
        viernes = lunes + timedelta(days=4)
        
        return lunes, viernes
    
    def cargar_candidatos_pendientes(self):
        """Carga candidatos pendientes de la semana de carga ordenados por nota (menor a mayor)"""
        print("\n📋 Cargando candidatos pendientes...")
        
        self.candidatos_pendientes = self.session.query(Candidato)\
            .filter(Candidato.semana_carga == self.semana_carga)\
            .filter(Candidato.estado == 'pendiente')\
            .order_by(Candidato.media_estudios.asc())\
            .all()
        
        self.estadisticas['candidatos_procesados'] = len(self.candidatos_pendientes)
        
        print(f"✅ {len(self.candidatos_pendientes)} candidatos pendientes encontrados (semana carga: {self.semana_carga})")
        
        if len(self.candidatos_pendientes) > 0:
            print(f"   📈 Rango de notas: {float(self.candidatos_pendientes[0].media_estudios):.2f} - {float(self.candidatos_pendientes[-1].media_estudios):.2f}")
        
        return len(self.candidatos_pendientes) > 0
    
    def cargar_franjas_disponibles(self):
        """Carga franjas reservadas de la semana de entrevistas con espacios disponibles"""
        print("\n🔍 Buscando franjas reservadas disponibles...")
        
        lunes, viernes = self.obtener_rango_fechas_semana()
        
        # Obtener todas las reservas de la semana de entrevistas
        reservas = self.session.query(Reserva)\
            .filter(Reserva.fecha >= lunes)\
            .filter(Reserva.fecha <= viernes)\
            .order_by(Reserva.fecha, Reserva.hora_inicio)\
            .all()
        
        print(f"   📅 Rango de fechas (semana entrevistas {self.semana_entrevistas}): {lunes.strftime('%d/%m/%Y')} - {viernes.strftime('%d/%m/%Y')}")
        print(f"   🔖 Total de reservas encontradas: {len(reservas)}")
        
        # Calcular capacidad disponible de cada reserva
        self.franjas_disponibles = []
        
        for reserva in reservas:
            # Contar cuántas asignaciones tiene esta reserva
            asignaciones_existentes = self.session.query(Asignacion)\
                .filter(Asignacion.reserva_id == reserva.id)\
                .count()
            
            espacios_libres = CONFIG['max_candidatos_por_franja'] - asignaciones_existentes
            
            if espacios_libres > 0:
                self.franjas_disponibles.append({
                    'reserva': reserva,
                    'espacios_libres': espacios_libres,
                    'asignaciones_actuales': asignaciones_existentes
                })
        
        print(f"✅ {len(self.franjas_disponibles)} franjas con espacios disponibles")
        
        # Mostrar resumen
        total_espacios = sum(f['espacios_libres'] for f in self.franjas_disponibles)
        print(f"   💺 Total de espacios disponibles: {total_espacios}")
        
        return len(self.franjas_disponibles) > 0
    
    def contar_asignaciones_por_profesor(self):
        """Cuenta cuántas asignaciones tiene cada profesor en esta semana"""
        lunes, viernes = self.obtener_rango_fechas_semana()
        
        resultado = self.session.query(
            Asignacion.entrevistador_id,
            func.count(Asignacion.id).label('cantidad')
        )\
        .join(Reserva)\
        .filter(Reserva.fecha >= lunes)\
        .filter(Reserva.fecha <= viernes)\
        .group_by(Asignacion.entrevistador_id)\
        .all()
        
        return {entrev_id: cantidad for entrev_id, cantidad in resultado}
    
    def asignar_candidatos(self):
        """Ejecuta el algoritmo de asignación balanceada"""
        print("\n🤖 Ejecutando algoritmo de asignación...")
        
        if not self.candidatos_pendientes:
            print("⚠️  No hay candidatos pendientes para asignar")
            return False
        
        if not self.franjas_disponibles:
            print("⚠️  No hay franjas disponibles para asignar")
            return False
        
        # Contar asignaciones actuales por profesor
        asignaciones_por_profesor = self.contar_asignaciones_por_profesor()
        
        # Índices para iterar
        idx_candidato = 0
        idx_franja = 0
        franjas_utilizadas = set()
        
        print(f"\n   🔄 Comenzando asignación de {len(self.candidatos_pendientes)} candidatos...")
        
        while idx_candidato < len(self.candidatos_pendientes) and idx_franja < len(self.franjas_disponibles):
            candidato = self.candidatos_pendientes[idx_candidato]
            franja = self.franjas_disponibles[idx_franja]
            reserva = franja['reserva']
            entrevistador_id = reserva.usuario_id
            
            # Verificar límite por profesor
            asignaciones_actuales = asignaciones_por_profesor.get(entrevistador_id, 0)
            
            if asignaciones_actuales >= self.max_por_profesor:
                print(f"   ⏭️  Profesor {reserva.usuario.username} alcanzó el límite ({self.max_por_profesor})")
                idx_franja += 1
                continue
            
            # Determinar posición y minuto de inicio
            if franja['asignaciones_actuales'] == 0:
                # Primera posición: minuto 0
                posicion = 1
                minuto_inicio = 0
            else:
                # Segunda posición: minuto 15
                posicion = 2
                minuto_inicio = 15
            
            # Crear asignación
            asignacion = Asignacion(
                candidato_id=candidato.id,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado='confirmado',
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=self.admin_user_id
            )
            
            self.session.add(asignacion)
            self.asignaciones_creadas.append(asignacion)
            
            # Actualizar contadores
            asignaciones_por_profesor[entrevistador_id] = asignaciones_actuales + 1
            franja['espacios_libres'] -= 1
            franja['asignaciones_actuales'] += 1
            franjas_utilizadas.add(reserva.id)
            
            # Mostrar progreso cada 10 asignaciones
            if (idx_candidato + 1) % 10 == 0:
                print(f"   ✅ {idx_candidato + 1}/{len(self.candidatos_pendientes)} candidatos asignados...")
            
            # Avanzar al siguiente candidato
            idx_candidato += 1
            
            # Si la franja se llenó, avanzar a la siguiente
            if franja['espacios_libres'] == 0:
                idx_franja += 1
        
        # Actualizar estadísticas
        self.estadisticas['candidatos_asignados'] = idx_candidato
        self.estadisticas['candidatos_sin_asignar'] = len(self.candidatos_pendientes) - idx_candidato
        self.estadisticas['franjas_utilizadas'] = len(franjas_utilizadas)
        
        print(f"\n✅ Asignación completada:")
        print(f"   • Candidatos asignados: {self.estadisticas['candidatos_asignados']}")
        print(f"   • Candidatos sin asignar: {self.estadisticas['candidatos_sin_asignar']}")
        print(f"   • Franjas utilizadas: {self.estadisticas['franjas_utilizadas']}")
        
        return True
    
    def mostrar_resumen(self):
        """Muestra un resumen de las asignaciones creadas"""
        if not self.asignaciones_creadas:
            print("\n⚠️  No hay asignaciones para mostrar")
            return
        
        print(f"\n📊 RESUMEN DE ASIGNACIONES ({len(self.asignaciones_creadas)}):")
        print("=" * 70)
        
        # Agrupar por entrevistador
        por_entrevistador = {}
        for asig in self.asignaciones_creadas:
            entrev_id = asig.entrevistador_id
            if entrev_id not in por_entrevistador:
                entrev_username = self.session.query(Usuario.username)\
                    .filter(Usuario.id == entrev_id)\
                    .scalar()
                por_entrevistador[entrev_id] = {
                    'username': entrev_username,
                    'asignaciones': []
                }
            
            candidato = self.session.query(Candidato)\
                .filter(Candidato.id == asig.candidato_id)\
                .first()
            
            por_entrevistador[entrev_id]['asignaciones'].append({
                'candidato': candidato,
                'reserva_id': asig.reserva_id,
                'posicion': asig.posicion
            })
        
        # Mostrar por entrevistador
        for entrev_id, data in por_entrevistador.items():
            print(f"\n👤 {data['username']} ({len(data['asignaciones'])} candidatos):")
            for asig in data['asignaciones']:
                cand = asig['candidato']
                print(f"   • {cand.nombre} {cand.apellidos} (Nota: {float(cand.media_estudios):.2f}) - Pos {asig['posicion']}")
        
        print("=" * 70)
    
    def guardar_en_bd(self, confirmar=True):
        """
        Guarda las asignaciones en la base de datos
        
        Args:
            confirmar (bool): Si True, pide confirmación
        
        Returns:
            bool: True si se guardó correctamente
        """
        if not self.asignaciones_creadas:
            print("\n⚠️  No hay asignaciones para guardar")
            return False
        
        if confirmar:
            print(f"\n❓ ¿Deseas guardar estas {len(self.asignaciones_creadas)} asignaciones en la base de datos?")
            respuesta = input("   Escribe 'SI' para confirmar: ").strip().upper()
            
            if respuesta != 'SI':
                print("❌ Operación cancelada por el usuario")
                self.session.rollback()
                return False
        
        print("\n💾 Guardando asignaciones en la base de datos...")
        
        try:
            # Commit de todas las asignaciones
            self.session.commit()
            
            print(f"✅ {len(self.asignaciones_creadas)} asignaciones guardadas correctamente")
            
            # Crear log de la ejecución
            tiempo_total = (datetime.now() - self.estadisticas['inicio']).total_seconds()
            
            log = LogAsignacion(
                fecha_ejecucion=datetime.now(),
                semana_objetivo=self.semana_carga,  # Guardamos semana_carga en el log
                candidatos_procesados=self.estadisticas['candidatos_procesados'],
                candidatos_filtrados=self.estadisticas['candidatos_filtrados'],
                candidatos_asignados=self.estadisticas['candidatos_asignados'],
                candidatos_sin_asignar=self.estadisticas['candidatos_sin_asignar'],
                franjas_utilizadas=self.estadisticas['franjas_utilizadas'],
                algoritmo_usado='balanceado',
                tiempo_ejecucion_segundos=round(tiempo_total, 2),
                estado='exito' if self.estadisticas['candidatos_sin_asignar'] == 0 else 'parcial',
                mensaje=f"Asignación completada. Candidatos semana {self.semana_carga} → Entrevistas semana {self.semana_entrevistas}. {self.estadisticas['candidatos_asignados']} asignados, {self.estadisticas['candidatos_sin_asignar']} sin asignar.",
                ejecutado_por_usuario_id=self.admin_user_id
            )
            
            self.session.add(log)
            self.session.commit()
            
            print(f"✅ Log de asignación registrado")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al guardar: {str(e)}")
            self.session.rollback()
            return False
    
    def ejecutar(self, auto_confirmar=False):
        """
        Ejecuta el proceso completo de asignación
        
        Args:
            auto_confirmar (bool): Si True, no pide confirmación
        
        Returns:
            bool: True si todo fue exitoso
        """
        print("\n🚀 INICIANDO PROCESO DE ASIGNACIÓN AUTOMÁTICA")
        print("=" * 70)
        
        try:
            # Paso 1: Cargar candidatos
            if not self.cargar_candidatos_pendientes():
                print("\n⚠️  No hay candidatos pendientes para asignar")
                return False
            
            # Paso 2: Cargar franjas
            if not self.cargar_franjas_disponibles():
                print("\n⚠️  No hay franjas disponibles")
                return False
            
            # Paso 3: Asignar
            if not self.asignar_candidatos():
                return False
            
            # Paso 4: Mostrar resumen
            self.mostrar_resumen()
            
            # Paso 5: Guardar
            if not self.guardar_en_bd(confirmar=not auto_confirmar):
                return False
            
            print("\n✅ PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            self.session.rollback()
            return False
        
        finally:
            self.session.close()


# ====================================================================
# FUNCIÓN PRINCIPAL
# ====================================================================

def main():
    """Función principal del script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Asigna candidatos a franjas reservadas automáticamente',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python asignar_candidatos.py --semana-carga 2024-W45
  python asignar_candidatos.py --semana-carga 2024-W45 --auto
  python asignar_candidatos.py --semana-carga 2024-W45 --max-por-profesor 10
  
Nota: Los candidatos de la semana-carga se asignarán a las reservas de la semana siguiente.
      Ejemplo: Candidatos W45 → Entrevistas W46
        """
    )
    
    parser.add_argument('--semana-carga', type=str, required=True,
                       help='Semana de carga de candidatos (formato: 2024-W45). Las entrevistas serán en la semana siguiente.')
    parser.add_argument('--max-por-profesor', type=int,
                       help='Máximo de candidatos por profesor')
    parser.add_argument('--auto', action='store_true',
                       help='Guardar automáticamente sin confirmación')
    parser.add_argument('--admin-id', type=int, default=1,
                       help='ID del usuario admin que ejecuta (default: 1)')
    
    args = parser.parse_args()
    
    # Crear asignador
    try:
        asignador = AsignadorCandidatos(
            semana_carga=args.semana_carga,
            max_por_profesor=args.max_por_profesor,
            admin_user_id=args.admin_id
        )
        
        # Ejecutar
        exito = asignador.ejecutar(auto_confirmar=args.auto)
        
        sys.exit(0 if exito else 1)
        
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ====================================================================
# PUNTO DE ENTRADA
# ====================================================================

if __name__ == '__main__':
    main()