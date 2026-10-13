"""
Constantes compartidas por varios módulos de rutas y servicios.

SEDES_DISPONIBLES vivía como una variable suelta en la cabecera del
app.py original (cerca de los modelos). La saco a su propio fichero
porque la usan tanto routes/usuarios.py (formularios de alta/edición)
como, potencialmente, otros módulos futuros — tenerla en un sitio
neutral evita que "quien la necesite" tenga que importarla desde una
ruta concreta.
"""

SEDES_DISPONIBLES = ["Bormujos", "Ciempozuelos", "Pº de la Habana"]