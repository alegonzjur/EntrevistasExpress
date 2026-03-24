# ====================================================================
# SCRIPT: CONVERTIR LOGO A BASE64
# ====================================================================

import base64
import os


def convertir_logo_a_base64(ruta_imagen):
    """
    Convierte una imagen a Base64 para usar en emails

    Args:
        ruta_imagen: Ruta al archivo de imagen (PNG, JPG, etc.)

    Returns:
        String con el código Base64 completo para usar en src
    """

    try:
        # Leer el archivo
        with open(ruta_imagen, "rb") as imagen_file:
            # Convertir a Base64
            imagen_base64 = base64.b64encode(imagen_file.read()).decode("utf-8")

        # Detectar tipo de imagen
        extension = os.path.splitext(ruta_imagen)[1].lower()

        if extension in [".png"]:
            mime_type = "image/png"
        elif extension in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif extension in [".gif"]:
            mime_type = "image/gif"
        elif extension in [".svg"]:
            mime_type = "image/svg+xml"
        else:
            mime_type = "image/png"  # Por defecto

        # Crear código completo
        codigo_completo = f"data:{mime_type};base64,{imagen_base64}"

        print("✅ Conversión exitosa!")
        print(f"\n📏 Longitud del código: {len(codigo_completo)} caracteres")
        print(f"🖼️  Tipo de imagen: {mime_type}")
        print("\n" + "=" * 70)
        print("CÓDIGO BASE64 (Copiar desde 'data:' hasta el final):")
        print("=" * 70)
        print(codigo_completo)
        print("=" * 70)

        # Guardar en archivo
        nombre_salida = f"{os.path.splitext(ruta_imagen)[0]}_base64.txt"
        with open(nombre_salida, "w", encoding="utf-8") as f:
            f.write(codigo_completo)

        print(f"\n💾 También guardado en: {nombre_salida}")

        return codigo_completo

    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo: {ruta_imagen}")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


# ====================================================================
# MODO DE USO
# ====================================================================

if __name__ == "__main__":
    print("🖼️  CONVERTIDOR DE LOGO A BASE64")
    print("=" * 70)

    # OPCIÓN 1: Ruta directa
    ruta_logo = r"./static/images/logoEuefHorizontal.png"

    # OPCIÓN 2: Pedir al usuario
    # ruta_logo = input("Ingresa la ruta completa del logo: ")

    codigo_base64 = convertir_logo_a_base64(ruta_logo)

    if codigo_base64:
        print("\n✅ COPIA EL CÓDIGO DE ARRIBA")
        print("   Y pégalo en el atributo src de la imagen en las funciones de email")
        print("\nEjemplo:")
        print('<img src="AQUI_PEGAR_EL_CODIGO_COMPLETO" alt="Logo" ...>')


# ====================================================================
# EJEMPLOS DE RUTAS COMUNES
# ====================================================================

# Windows:
# r"C:\Users\TuUsuario\Desktop\logo.png"
# r"C:\Users\Alejandro-admin\Desktop\logo_fundacion.png"

# Linux/Mac:
# "/home/usuario/logo.png"
# "/Users/usuario/Desktop/logo.png"
