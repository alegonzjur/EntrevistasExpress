"""Validación de ficheros subidos (Excel de candidatos)."""

ALLOWED_EXTENSIONS = {"xlsx", "xls"}


def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS