// ====================================================================
// FUNCIONES DE ALERTAS CON SWEETALERT2
// ====================================================================

/**
 * Alerta de éxito
 */
function mostrarExito(mensaje, titulo = '¡Éxito!') {
    return Swal.fire({
        icon: 'success',
        title: titulo,
        text: mensaje,
        confirmButtonColor: '#28a745',
        confirmButtonText: 'Aceptar',
        timer: 3000,
        timerProgressBar: true
    });
}

/**
 * Alerta de error
 */
function mostrarError(mensaje, titulo = 'Error') {
    return Swal.fire({
        icon: 'error',
        title: titulo,
        text: mensaje,
        confirmButtonColor: '#dc3545',
        confirmButtonText: 'Entendido'
    });
}

/**
 * Alerta de advertencia
 */
function mostrarAdvertencia(mensaje, titulo = 'Atención') {
    return Swal.fire({
        icon: 'warning',
        title: titulo,
        text: mensaje,
        confirmButtonColor: '#ffc107',
        confirmButtonText: 'Entendido'
    });
}

/**
 * Alerta de información
 */
function mostrarInfo(mensaje, titulo = 'Información') {
    return Swal.fire({
        icon: 'info',
        title: titulo,
        text: mensaje,
        confirmButtonColor: '#17a2b8',
        confirmButtonText: 'Aceptar'
    });
}

/**
 * Confirmación (Sí/No)
 */
function confirmar(mensaje, titulo = '¿Estás seguro?', textoConfirmar = 'Sí, continuar', textoCancelar = 'Cancelar') {
    return Swal.fire({
        icon: 'question',
        title: titulo,
        text: mensaje,
        showCancelButton: true,
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#6c757d',
        confirmButtonText: textoConfirmar,
        cancelButtonText: textoCancelar,
        reverseButtons: true
    });
}

/**
 * Confirmación de eliminación
 */
function confirmarEliminacion(mensaje = '¿Deseas eliminar este elemento?', titulo = '¿Eliminar?') {
    return Swal.fire({
        icon: 'warning',
        title: titulo,
        text: mensaje,
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    });
}

/**
 * Toast notification (pequeña notificación en esquina)
 */
function mostrarToast(mensaje, icono = 'success') {
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    return Toast.fire({
        icon: icono,
        title: mensaje
    });
}

/**
 * Loading (cargando...)
 */
function mostrarCargando(mensaje = 'Procesando...') {
    Swal.fire({
        title: mensaje,
        allowOutsideClick: false,
        allowEscapeKey: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
}

/**
 * Cerrar loading
 */
function cerrarCargando() {
    Swal.close();
}

/**
 * Alerta con HTML personalizado
 */
function mostrarHTML(html, titulo = '') {
    return Swal.fire({
        title: titulo,
        html: html,
        confirmButtonColor: '#0066B3',
        confirmButtonText: 'Aceptar'
    });
}

/**
 * Input de texto
 */
function pedirTexto(mensaje, titulo = 'Ingresa un valor', placeholder = '') {
    return Swal.fire({
        title: titulo,
        text: mensaje,
        input: 'text',
        inputPlaceholder: placeholder,
        showCancelButton: true,
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Aceptar',
        cancelButtonText: 'Cancelar',
        inputValidator: (value) => {
            if (!value) {
                return 'Este campo es obligatorio';
            }
        }
    });
}