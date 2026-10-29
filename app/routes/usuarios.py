"""
Administración de cuentas de usuario: alta, listado, activar/desactivar,
editar, eliminar, cambiar rol, y el panel de estadísticas generales
(que mezcla datos de Usuario y Reserva, pero encaja mejor aquí que en
routes/reservas.py porque su protagonista es la vista de administración
de usuarios, justo al lado de la que estaba en el app.py original).
"""

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app.constants import SEDES_DISPONIBLES
from app.extensions import db
from app.models import Reserva, Sede, Usuario
from app.services.logs import registrar_log
from app.utils.decorators import admin_required


def register(app):
    @app.route("/registro", methods=["GET", "POST"])
    @admin_required
    def registro():
        if request.method == "POST":
            username = request.form["username"]
            email = request.form["email"]
            nombre_completo = request.form.get("nombre_completo", "").strip()
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            rol = request.form.get("rol", "profesor")
            sedes_seleccionadas = request.form.getlist("sedes[]")

            # ========================================
            # VALIDACIONES
            # ========================================

            if not nombre_completo:
                flash("El nombre completo es requerido", "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # Validar longitud de contraseña
            if len(password) < 6:
                flash("La contraseña debe tener al menos 6 caracteres", "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # Validar que las contraseñas coincidan
            if password != confirm_password:
                flash("Las contraseñas no coinciden", "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # Verificar si ya existe el username
            if Usuario.query.filter_by(username=username).first():
                flash(f'El nombre de usuario "{username}" ya está en uso', "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # Verificar si ya existe el email
            if Usuario.query.filter_by(email=email).first():
                flash(f'El email "{email}" ya está registrado', "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # Validar sede si es profesor
            if rol == "profesor" and not sedes_seleccionadas:
                flash("Debes seleccionar al menos una sede para el profesor", "error")
                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

            # ========================================
            # CREAR USUARIO
            # ========================================
            try:
                nuevo_usuario = Usuario(
                    username=username,
                    email=email,
                    nombre_completo=nombre_completo,
                    password=generate_password_hash(password),
                    rol=rol,
                    sede=sedes_seleccionadas[0] if sedes_seleccionadas else None,
                )

                db.session.add(nuevo_usuario)
                db.session.flush()  # Para obtener el ID

                # Asignar sedes al profesor
                if rol == "profesor" and sedes_seleccionadas:
                    for sede_nombre in sedes_seleccionadas:
                        sede = Sede.query.filter_by(nombre=sede_nombre).first()
                        if sede:
                            nuevo_usuario.sedes.append(sede)

                db.session.commit()

                registrar_log(
                    accion="crear",
                    entidad="usuario",
                    entidad_id=nuevo_usuario.id,
                    descripcion=f'Usuario creado: {username} ({nombre_completo}) - Rol: {rol} - Sedes: {", ".join(sedes_seleccionadas)}',
                    datos_nuevos={
                        "username": username,
                        "email": email,
                        "nombre_completo": nombre_completo,
                        "rol": rol,
                        "sedes": sedes_seleccionadas,
                    },
                    nivel="info",
                )

                flash(f"Usuario {username} creado correctamente", "success")
                return redirect(url_for("admin_usuarios"))

            except Exception as e:
                db.session.rollback()

                error_msg = str(e).lower()

                if "usuarios_username_key" in error_msg or "username" in error_msg:
                    flash(f'El nombre de usuario "{username}" ya está en uso', "error")
                elif "usuarios_email_key" in error_msg or "email" in error_msg:
                    flash(f'El email "{email}" ya está registrado', "error")
                else:
                    flash(f"Error al crear usuario: {str(e)}", "error")

                return render_template(
                    "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
                )

        return render_template(
            "registro.html", username=session["username"], sedes=SEDES_DISPONIBLES
        )

    @app.route("/admin/usuarios")
    @admin_required
    def admin_usuarios():
        usuarios = Usuario.query.order_by(Usuario.fecha_creacion.desc()).all()
        return render_template(
            "admin_usuarios.html",
            usuarios=usuarios,
            username=session["username"],
            sedes=SEDES_DISPONIBLES,
        )

    @app.route("/admin/usuario/toggle/<int:usuario_id>", methods=["POST"])
    @admin_required
    def toggle_usuario(usuario_id):
        usuario = Usuario.query.get_or_404(usuario_id)

        if usuario.id == session["user_id"]:
            return jsonify({"error": "No puedes desactivar tu propia cuenta"}), 400

        usuario.activo = not usuario.activo
        db.session.commit()

        estado = "activado" if usuario.activo else "desactivado"
        return jsonify(
            {
                "success": True,
                "mensaje": f"Usuario {usuario.username} {estado}",
                "activo": usuario.activo,
            }
        )

    @app.route("/admin/usuarios/editar/<int:usuario_id>", methods=["GET", "POST"])
    @admin_required
    def editar_usuario(usuario_id):
        """Editar información de un usuario"""

        usuario = Usuario.query.get_or_404(usuario_id)

        if request.method == "POST":
            email_nuevo = request.form.get("email")
            nombre_completo_nuevo = request.form.get("nombre_completo", "").strip()
            rol_nuevo = request.form.get("rol")
            sedes_seleccionadas = request.form.getlist("sedes")

            nueva_contrasena = request.form.get("nueva_contrasena", "").strip()
            confirmar_contrasena = request.form.get("confirmar_contrasena", "").strip()

            # Enlace de videollamada personal: lo puede añadir/sobrescribir
            # un admin desde aquí (antes solo lo podía tocar el propio
            # profesor desde /perfil). En blanco significa "no toques el
            # que ya hay" — nunca borra el enlace existente.
            enlace_videollamada_nuevo = request.form.get(
                "enlace_videollamada_personal", ""
            ).strip()
            if enlace_videollamada_nuevo and not (
                enlace_videollamada_nuevo.startswith("http://")
                or enlace_videollamada_nuevo.startswith("https://")
            ):
                enlace_videollamada_nuevo = "https://" + enlace_videollamada_nuevo

            # Validar nombre completo
            if not nombre_completo_nuevo:
                flash("El nombre completo es requerido", "error")
                todas_sedes = Sede.query.filter_by(activa=True).all()
                return render_template(
                    "editar_usuario.html",
                    usuario=usuario,
                    username=session["username"],
                    todas_sedes=todas_sedes,
                )

            # Guardar valores anteriores para el log
            datos_anteriores = {
                "email": usuario.email,
                "nombre_completo": usuario.nombre_completo,
                "rol": usuario.rol,
                "sedes": [s.nombre for s in usuario.sedes],
                "enlace_videollamada_personal": usuario.enlace_videollamada_personal,
            }

            # ========================================
            # VALIDACIÓN DE CONTRASEÑA
            # ========================================
            if nueva_contrasena or confirmar_contrasena:
                if not nueva_contrasena or not confirmar_contrasena:
                    flash("Debes completar ambos campos de contraseña", "error")
                    todas_sedes = Sede.query.filter_by(activa=True).all()
                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario,
                        username=session["username"],
                        todas_sedes=todas_sedes,
                    )

                if nueva_contrasena != confirmar_contrasena:
                    flash("Las contraseñas no coinciden", "error")
                    todas_sedes = Sede.query.filter_by(activa=True).all()
                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario,
                        username=session["username"],
                        todas_sedes=todas_sedes,
                    )

                if len(nueva_contrasena) < 6:
                    flash("La contraseña debe tener al menos 6 caracteres", "error")
                    todas_sedes = Sede.query.filter_by(activa=True).all()
                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario,
                        username=session["username"],
                        todas_sedes=todas_sedes,
                    )

                # Cambiar contraseña
                usuario.password = generate_password_hash(nueva_contrasena)
                datos_anteriores["cambio_contrasena"] = False

            # ========================================
            # VALIDACIÓN DE EMAIL DUPLICADO
            # ========================================
            if email_nuevo != usuario.email:
                email_existente = Usuario.query.filter(
                    Usuario.email == email_nuevo, Usuario.id != usuario_id
                ).first()

                if email_existente:
                    flash(
                        f"El email {email_nuevo} ya está en uso por otro usuario", "error"
                    )
                    todas_sedes = Sede.query.filter_by(activa=True).all()
                    return render_template(
                        "editar_usuario.html",
                        usuario=usuario,
                        username=session["username"],
                        todas_sedes=todas_sedes,
                    )

            # Actualizar email, nombre_completo y rol
            usuario.email = email_nuevo
            usuario.nombre_completo = nombre_completo_nuevo
            usuario.rol = rol_nuevo

            # Solo se sobrescribe si se introdujo un enlace nuevo; en
            # blanco se deja el que ya hubiera tal cual.
            if enlace_videollamada_nuevo:
                usuario.enlace_videollamada_personal = enlace_videollamada_nuevo

            # Actualizar sedes (relación muchos-a-muchos)
            if rol_nuevo == "profesor" and sedes_seleccionadas:
                usuario.sedes = []
                for sede_nombre in sedes_seleccionadas:
                    sede = Sede.query.filter_by(nombre=sede_nombre).first()
                    if sede:
                        usuario.sedes.append(sede)
            else:
                usuario.sedes = []

            # ========================================
            # GUARDAR CON MANEJO DE ERRORES
            # ========================================
            try:
                db.session.commit()

                datos_nuevos = {
                    "email": email_nuevo,
                    "nombre_completo": nombre_completo_nuevo,
                    "rol": rol_nuevo,
                    "sedes": (
                        [s.nombre for s in usuario.sedes] if rol_nuevo == "profesor" else []
                    ),
                    "enlace_videollamada_personal": usuario.enlace_videollamada_personal,
                }

                if nueva_contrasena:
                    datos_nuevos["cambio_contrasena"] = True

                registrar_log(
                    accion="modificar",
                    entidad="usuario",
                    entidad_id=usuario.id,
                    descripcion=f"Usuario modificado: {usuario.username} ({nombre_completo_nuevo})"
                    + (" (contraseña cambiada)" if nueva_contrasena else ""),
                    datos_anteriores=datos_anteriores,
                    datos_nuevos=datos_nuevos,
                    nivel="info",
                )

                mensaje_exito = f"Usuario {usuario.username} actualizado correctamente"
                if nueva_contrasena:
                    mensaje_exito += ". Contraseña cambiada exitosamente"

                flash(mensaje_exito, "success")
                return redirect(url_for("admin_usuarios"))

            except Exception as e:
                db.session.rollback()

                if "usuarios_email_key" in str(e) or "duplicate key" in str(e).lower():
                    flash(
                        f"El email {email_nuevo} ya está en uso por otro usuario", "error"
                    )
                else:
                    flash(f"Error al actualizar usuario: {str(e)}", "error")

                todas_sedes = Sede.query.filter_by(activa=True).all()
                return render_template(
                    "editar_usuario.html",
                    usuario=usuario,
                    username=session["username"],
                    todas_sedes=todas_sedes,
                )

        # GET: Mostrar formulario
        todas_sedes = Sede.query.filter_by(activa=True).all()

        return render_template(
            "editar_usuario.html",
            usuario=usuario,
            username=session["username"],
            todas_sedes=todas_sedes,
        )

    @app.route("/admin/usuario/eliminar/<int:usuario_id>", methods=["POST"])
    @admin_required
    def eliminar_usuario(usuario_id):
        usuario = Usuario.query.get_or_404(usuario_id)

        if usuario.id == session["user_id"]:
            return jsonify({"error": "No puedes eliminar tu propia cuenta"}), 400

        Reserva.query.filter_by(usuario_id=usuario_id).delete()

        db.session.delete(usuario)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "mensaje": f"Usuario {usuario.username} eliminado correctamente",
            }
        )

    @app.route("/admin/usuario/cambiar-rol/<int:usuario_id>", methods=["POST"])
    @admin_required
    def cambiar_rol_usuario(usuario_id):
        usuario = Usuario.query.get_or_404(usuario_id)

        if usuario.id == session["user_id"]:
            return jsonify({"error": "No puedes cambiar tu propio rol"}), 400

        nuevo_rol = "admin" if usuario.rol == "profesor" else "profesor"
        usuario.rol = nuevo_rol
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "mensaje": f"Rol de {usuario.username} cambiado a {nuevo_rol}",
                "rol": nuevo_rol,
            }
        )

    @app.route("/admin/estadisticas")
    @admin_required
    def admin_estadisticas():
        total_usuarios = Usuario.query.count()
        total_profesores = Usuario.query.filter_by(rol="profesor").count()
        total_admins = Usuario.query.filter_by(rol="admin").count()
        usuarios_activos = Usuario.query.filter_by(activo=True).count()

        total_reservas = Reserva.query.count()

        sede_filtro = request.args.get("sede", "")
        sedes_disponibles = (
            Sede.query.filter_by(activa=True).order_by(Sede.nombre).all()
        )

        reservas_por_usuario_todos = (
            db.session.query(Usuario, func.count(Reserva.id).label("total"))
            # Join explícito: Usuario tiene dos relaciones FK hacia Reserva
            # (usuario_id y creado_por_admin), así que un .join(Reserva) sin
            # condición es ambiguo para SQLAlchemy y lanza
            # AmbiguousForeignKeysError. Esto es un bug heredado del app.py
            # original (ahí tampoco se especificaba), no algo introducido en
            # esta extracción. Aquí lo fijamos a "reservas hechas por el
            # propio usuario", que es la lectura que tiene sentido para esta
            # estadística.
            .join(Reserva, Reserva.usuario_id == Usuario.id)
            .group_by(Usuario.id)
            .order_by(func.count(Reserva.id).desc())
            .all()
        )

        # No es "modo competición" (ya no hay Top 10): se listan todos los
        # profesores con reservas, de mayor a menor, y se puede acotar a
        # una sede concreta — un profesor puede atender varias sedes
        # (reutilizamos la misma lógica que ya decide, en el algoritmo de
        # asignación, si un profesor puede atender una sede dada).
        if sede_filtro:
            reservas_por_usuario = [
                (usuario, total)
                for usuario, total in reservas_por_usuario_todos
                if usuario.puede_atender_sede(sede_filtro)
            ]
        else:
            reservas_por_usuario = reservas_por_usuario_todos

        return render_template(
            "admin_estadisticas.html",
            total_usuarios=total_usuarios,
            total_profesores=total_profesores,
            total_admins=total_admins,
            usuarios_activos=usuarios_activos,
            total_reservas=total_reservas,
            reservas_por_usuario=reservas_por_usuario,
            sedes_disponibles=sedes_disponibles,
            sede_filtro=sede_filtro,
            username=session["username"],
        )