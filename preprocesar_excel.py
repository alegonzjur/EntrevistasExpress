#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de preprocesamiento de Excel de Candidatos
Sistema de Reservas - Fundación San Juan de Dios

Este script:
1. Lee el archivo Excel de calificaciones
2. Extrae las columnas relevantes
3. Filtra candidatos con nota < umbral definido
4. Limpia y valida los datos
5. Guarda los candidatos en la base de datos
6. Genera un reporte detallado

Uso:
    python preprocesar_excel.py ruta/al/archivo.xlsx
    python preprocesar_excel.py ruta/al/archivo.xlsx --umbral 7.5
    python preprocesar_excel.py ruta/al/archivo.xlsx --semana 2024-W46
"""

import pandas as pd
import sys
import os
import hashlib
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ====================================================================
# CONFIGURACIÓN
# ====================================================================

# Configuración de la base de datos (ajustar según tu configuración)
DATABASE_URI = 'postgresql://postgres:eebormujos?@localhost/reservas_db'

# Configuración del procesamiento
CONFIG = {
    'fila_encabezados': 23,  # Fila 24 en Excel (índice 23 en pandas)
    'umbral_nota': 7.0,       # Solo candidatos con nota < 7.0
    'columnas_excel': {
        'solicitud': 'Solicitud',
        'apellidos': 'Apellidos',
        'nombre': 'Nombre',
        'media_estudios': 'Media estudios realizados',
        'primera_opcion': 'Primera opción'
    }
}

# ====================================================================
# CLASE PRINCIPAL
# ====================================================================

class ProcesadorExcelCandidatos:
    """Procesa archivos Excel de candidatos y los carga en la BD"""
    
    def __init__(self, archivo_excel, umbral_nota=None, semana_carga=None):
        """
        Inicializa el procesador
        
        Args:
            archivo_excel (str): Ruta al archivo Excel
            umbral_nota (float): Umbral de nota (default: 7.0)
            semana_carga (str): Semana en formato 2024-W46 (default: semana actual)
        """
        self.archivo_excel = archivo_excel
        self.umbral_nota = umbral_nota or CONFIG['umbral_nota']
        self.semana_carga = semana_carga or self._calcular_semana_actual()
        
        # Verificar que el archivo existe
        if not os.path.exists(archivo_excel):
            raise FileNotFoundError(f"El archivo {archivo_excel} no existe")
        
        # Variables de estado
        self.df_original = None
        self.df_procesado = None
        self.reporte = {}
        
        print(f"📁 Archivo: {os.path.basename(archivo_excel)}")
        print(f"📊 Umbral de nota: < {self.umbral_nota}")
        print(f"📅 Semana: {self.semana_carga}")
        print("=" * 70)
    
    def _calcular_semana_actual(self):
        """Calcula la semana actual en formato ISO (2024-W46)"""
        return datetime.now().strftime('%Y-W%W')
    
    def _calcular_hash_archivo(self):
        """Calcula el hash MD5 del archivo para detectar duplicados"""
        hash_md5 = hashlib.md5()
        with open(self.archivo_excel, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def leer_excel(self):
        """Lee el archivo Excel desde la fila correcta"""
        print("\n📖 Leyendo archivo Excel...")
        
        try:
            # Leer desde la fila 24 (índice 23)
            self.df_original = pd.read_excel(
                self.archivo_excel,
                header=CONFIG['fila_encabezados']
            )
            
            print(f"✅ Archivo leído correctamente")
            print(f"   Total de filas: {len(self.df_original)}")
            print(f"   Total de columnas: {len(self.df_original.columns)}")
            
            # Verificar que existen las columnas necesarias
            columnas_necesarias = list(CONFIG['columnas_excel'].values())
            columnas_faltantes = [col for col in columnas_necesarias if col not in self.df_original.columns]
            
            if columnas_faltantes:
                raise ValueError(f"Columnas faltantes en el Excel: {columnas_faltantes}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al leer el archivo: {str(e)}")
            return False
    
    def procesar_datos(self):
        """Procesa y limpia los datos del Excel"""
        print("\n🔧 Procesando datos...")
        
        # Seleccionar solo las columnas necesarias
        columnas = CONFIG['columnas_excel']
        df = self.df_original[[
            columnas['solicitud'],
            columnas['apellidos'],
            columnas['nombre'],
            columnas['media_estudios'],
            columnas['primera_opcion']
        ]].copy()
        
        # Renombrar columnas a formato de BD
        df.rename(columns={
            columnas['solicitud']: 'solicitud',
            columnas['apellidos']: 'apellidos',
            columnas['nombre']: 'nombre',
            columnas['media_estudios']: 'media_estudios',
            columnas['primera_opcion']: 'primera_opcion'
        }, inplace=True)
        
        # Estadísticas iniciales
        total_original = len(df)
        
        # 1. Eliminar filas con valores nulos en campos críticos
        df = df.dropna(subset=['solicitud', 'apellidos', 'nombre', 'media_estudios'])
        sin_nulos = len(df)
        
        # 2. Limpiar y validar datos
        df['apellidos'] = df['apellidos'].astype(str).str.strip()
        df['nombre'] = df['nombre'].astype(str).str.strip()
        df['solicitud'] = pd.to_numeric(df['solicitud'], errors='coerce')
        df['media_estudios'] = pd.to_numeric(df['media_estudios'], errors='coerce')
        
        # 3. Eliminar filas con conversiones fallidas
        df = df.dropna(subset=['solicitud', 'media_estudios'])
        con_datos_validos = len(df)
        
        # 4. Filtrar por umbral de nota
        df_filtrado = df[df['media_estudios'] < self.umbral_nota].copy()
        
        # 5. Añadir campos de gestión
        df_filtrado['email'] = None
        df_filtrado['estado'] = 'pendiente'
        df_filtrado['fecha_carga'] = datetime.now()
        df_filtrado['semana_carga'] = self.semana_carga
        df_filtrado['archivo_origen'] = os.path.basename(self.archivo_excel)
        
        self.df_procesado = df_filtrado
        
        # Guardar estadísticas
        self.reporte = {
            'total_leidos': total_original,
            'sin_valores_nulos': sin_nulos,
            'con_datos_validos': con_datos_validos,
            'filtrados_por_nota_alta': con_datos_validos - len(df_filtrado),
            'candidatos_finales': len(df_filtrado),
            'nota_minima': float(df_filtrado['media_estudios'].min()) if len(df_filtrado) > 0 else None,
            'nota_maxima': float(df_filtrado['media_estudios'].max()) if len(df_filtrado) > 0 else None,
            'nota_promedio': float(df_filtrado['media_estudios'].mean()) if len(df_filtrado) > 0 else None
        }
        
        # Mostrar resumen
        print(f"✅ Datos procesados correctamente")
        print(f"\n📊 RESUMEN DEL PROCESAMIENTO:")
        print(f"   • Total leídos del Excel: {self.reporte['total_leidos']}")
        print(f"   • Sin valores nulos: {self.reporte['sin_valores_nulos']}")
        print(f"   • Con datos válidos: {self.reporte['con_datos_validos']}")
        print(f"   • Filtrados por nota >= {self.umbral_nota}: {self.reporte['filtrados_por_nota_alta']}")
        print(f"   • ✅ CANDIDATOS VÁLIDOS: {self.reporte['candidatos_finales']}")
        
        if self.reporte['candidatos_finales'] > 0:
            print(f"\n   📈 Rango de notas:")
            print(f"      - Mínima: {self.reporte['nota_minima']:.2f}")
            print(f"      - Máxima: {self.reporte['nota_maxima']:.2f}")
            print(f"      - Promedio: {self.reporte['nota_promedio']:.2f}")
        
        return len(df_filtrado) > 0
    
    def mostrar_candidatos(self):
        """Muestra los candidatos procesados"""
        if self.df_procesado is None or len(self.df_procesado) == 0:
            print("\n⚠️  No hay candidatos para mostrar")
            return
        
        print(f"\n📋 CANDIDATOS A IMPORTAR ({len(self.df_procesado)}):")
        print("=" * 70)
        
        for idx, row in self.df_procesado.iterrows():
            print(f"{row['solicitud']:3.0f} | {row['nombre']:15s} {row['apellidos']:20s} | Nota: {row['media_estudios']:.2f}")
        
        print("=" * 70)
    
    def guardar_en_bd(self, confirmar=True):
        """
        Guarda los candidatos en la base de datos
        
        Args:
            confirmar (bool): Si True, pide confirmación antes de guardar
        
        Returns:
            bool: True si se guardó correctamente, False si no
        """
        if self.df_procesado is None or len(self.df_procesado) == 0:
            print("\n⚠️  No hay candidatos para guardar")
            return False
        
        # Pedir confirmación
        if confirmar:
            print(f"\n❓ ¿Deseas guardar estos {len(self.df_procesado)} candidatos en la base de datos?")
            respuesta = input("   Escribe 'SI' para confirmar: ").strip().upper()
            
            if respuesta != 'SI':
                print("❌ Operación cancelada por el usuario")
                return False
        
        print("\n💾 Guardando en la base de datos...")
        
        try:
            # Crear conexión a la base de datos con codificación UTF-8
            engine = create_engine(
                DATABASE_URI,
                connect_args={'client_encoding': 'utf8'}
            )
            
            # Verificar duplicados antes de insertar
            from sqlalchemy import text
            with engine.connect() as conn:
                # Verificar si ya existen candidatos de esta semana
                result = conn.execute(
                    text("SELECT COUNT(*) FROM candidatos WHERE semana_carga = :semana"),
                    {"semana": self.semana_carga}
                )
                existentes = result.scalar()
                
                if existentes > 0:
                    print(f"\n⚠️  ADVERTENCIA: Ya existen {existentes} candidatos para la semana {self.semana_carga}")
                    respuesta = input("   ¿Deseas continuar de todas formas? (SI/NO): ").strip().upper()
                    if respuesta != 'SI':
                        print("❌ Operación cancelada")
                        return False
            
            # Limpiar caracteres problemáticos en todas las columnas de texto
            for col in ['apellidos', 'nombre', 'primera_opcion', 'archivo_origen']:
                if col in self.df_procesado.columns:
                    self.df_procesado[col] = self.df_procesado[col].apply(
                        lambda x: str(x).encode('utf-8', 'ignore').decode('utf-8') if x is not None and str(x) != 'nan' else x
                    )
            
            # Guardar en la tabla candidatos con método más robusto
            self.df_procesado.to_sql(
                'candidatos',
                engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=100
            )
            
            print(f"✅ {len(self.df_procesado)} candidatos guardados correctamente")
            
            # Registrar la carga en la tabla cargas_excel
            hash_archivo = self._calcular_hash_archivo()
            
            mensaje = f"Importación exitosa. {self.reporte['candidatos_finales']} candidatos con nota < {self.umbral_nota}"
            mensaje = mensaje.encode('utf-8', 'ignore').decode('utf-8')
            
            carga_excel_data = pd.DataFrame([{
                'archivo_nombre': os.path.basename(self.archivo_excel),
                'archivo_hash': hash_archivo,
                'fecha_carga': datetime.now(),
                'candidatos_totales': self.reporte['total_leidos'],
                'candidatos_importados': self.reporte['candidatos_finales'],
                'candidatos_duplicados': 0,
                'semana_destino': self.semana_carga,
                'estado': 'completado',
                'mensaje': mensaje
            }])
            
            carga_excel_data.to_sql(
                'cargas_excel',
                engine,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            print(f"✅ Registro de carga guardado en cargas_excel")
            
            # Cerrar conexión
            engine.dispose()
            
            return True
            
        except Exception as e:
            print(f"❌ Error al guardar en la base de datos: {str(e)}")
            import traceback
            print("\n🔍 Detalles del error:")
            traceback.print_exc()
            return False
    
    def generar_reporte_txt(self):
        """Genera un archivo de texto con el reporte detallado"""
        if not self.reporte:
            print("⚠️  No hay reporte para generar")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_reporte = f"reporte_candidatos_{timestamp}.txt"
        
        with open(nombre_reporte, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("REPORTE DE PROCESAMIENTO DE CANDIDATOS\n")
            f.write("Sistema de Reservas - Fundación San Juan de Dios\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"📁 Archivo procesado: {os.path.basename(self.archivo_excel)}\n")
            f.write(f"📅 Fecha de procesamiento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"📊 Umbral de nota: < {self.umbral_nota}\n")
            f.write(f"📆 Semana de carga: {self.semana_carga}\n\n")
            
            f.write("ESTADÍSTICAS:\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total de registros leídos:        {self.reporte['total_leidos']}\n")
            f.write(f"Registros sin valores nulos:      {self.reporte['sin_valores_nulos']}\n")
            f.write(f"Registros con datos válidos:      {self.reporte['con_datos_validos']}\n")
            f.write(f"Filtrados por nota alta:          {self.reporte['filtrados_por_nota_alta']}\n")
            f.write(f"CANDIDATOS FINALES:               {self.reporte['candidatos_finales']}\n\n")
            
            if self.reporte['candidatos_finales'] > 0:
                f.write(f"Nota mínima:    {self.reporte['nota_minima']:.2f}\n")
                f.write(f"Nota máxima:    {self.reporte['nota_maxima']:.2f}\n")
                f.write(f"Nota promedio:  {self.reporte['nota_promedio']:.2f}\n\n")
            
            if self.df_procesado is not None and len(self.df_procesado) > 0:
                f.write("\nCANDIDATOS PROCESADOS:\n")
                f.write("-" * 70 + "\n")
                for idx, row in self.df_procesado.iterrows():
                    f.write(f"{int(row['solicitud']):3d} | {row['nombre']:15s} {row['apellidos']:20s} | Nota: {row['media_estudios']:.2f}\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write("Fin del reporte\n")
        
        print(f"\n📄 Reporte generado: {nombre_reporte}")
    
    def ejecutar(self, guardar=True, generar_reporte=True):
        """
        Ejecuta el proceso completo
        
        Args:
            guardar (bool): Si True, guarda en BD
            generar_reporte (bool): Si True, genera archivo de reporte
        
        Returns:
            bool: True si todo fue exitoso
        """
        print("\n🚀 INICIANDO PROCESAMIENTO DE CANDIDATOS")
        print("=" * 70)
        
        # Paso 1: Leer Excel
        if not self.leer_excel():
            return False
        
        # Paso 2: Procesar datos
        if not self.procesar_datos():
            print("\n⚠️  No hay candidatos que cumplan los criterios")
            return False
        
        # Paso 3: Mostrar candidatos
        self.mostrar_candidatos()
        
        # Paso 4: Guardar en BD
        if guardar:
            if not self.guardar_en_bd(confirmar=True):
                return False
        
        # Paso 5: Generar reporte
        if generar_reporte:
            self.generar_reporte_txt()
        
        print("\n✅ PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        
        return True


# ====================================================================
# FUNCIÓN PRINCIPAL
# ====================================================================

def main():
    """Función principal del script"""
    import argparse
    
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description='Procesa archivo Excel de candidatos y los carga en la BD',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python preprocesar_excel.py calificaciones.xlsx
  python preprocesar_excel.py calificaciones.xlsx --umbral 7.5
  python preprocesar_excel.py calificaciones.xlsx --semana 2024-W46
  python preprocesar_excel.py calificaciones.xlsx --no-guardar
        """
    )
    
    parser.add_argument('archivo', help='Ruta al archivo Excel')
    parser.add_argument('--umbral', type=float, default=7.0,
                       help='Umbral de nota (default: 7.0)')
    parser.add_argument('--semana', type=str,
                       help='Semana de carga (formato: 2024-W46). Default: semana actual')
    parser.add_argument('--no-guardar', action='store_true',
                       help='Solo procesar sin guardar en BD')
    parser.add_argument('--no-reporte', action='store_true',
                       help='No generar archivo de reporte')
    
    args = parser.parse_args()
    
    # Crear procesador
    try:
        procesador = ProcesadorExcelCandidatos(
            args.archivo,
            umbral_nota=args.umbral,
            semana_carga=args.semana
        )
        
        # Ejecutar
        exito = procesador.ejecutar(
            guardar=not args.no_guardar,
            generar_reporte=not args.no_reporte
        )
        
        # Retornar código de salida
        sys.exit(0 if exito else 1)
        
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {str(e)}")
        sys.exit(1)


# ====================================================================
# PUNTO DE ENTRADA
# ====================================================================

if __name__ == '__main__':
    main()