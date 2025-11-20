# 📧 GUÍA COMPLETA - SISTEMA DE EMAILS CON OFFICE 365

## 📋 ARCHIVOS GENERADOS

1. **limpiar_base_datos.py** - Script para limpiar datos de prueba
2. **sistema_emails_flask.py** - Código Python completo del sistema
3. **templates_emails_actualizaciones.html** - Actualizaciones para templates
4. **Esta guía de instalación**

---

## 🚀 INSTALACIÓN PASO A PASO

### **PASO 1: Instalar dependencias**

```bash
pip install flask-mail
```

**Verificar:**
```bash
pip list | grep Flask-Mail
# Debe mostrar: Flask-Mail  x.x.x
```

---

### **PASO 2: Configurar Office 365**

#### **Opción A: Con cuenta personal (@tuuniversidad.edu)**

```python
# En app.py, después de app = Flask(__name__):

app.config['MAIL_SERVER'] = 'smtp.office365.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'tu_email@tuuniversidad.edu'  # ← TU EMAIL
app.config['MAIL_PASSWORD'] = 'tu_contraseña'  # ← TU CONTRASEÑA
app.config['MAIL_DEFAULT_SENDER'] = 'tu_email@tuuniversidad.edu'
```

**⚠️ IMPORTANTE:**
- Si tienes 2FA (autenticación de dos factores), necesitas una **contraseña de aplicación**
- NO uses tu contraseña normal si tienes 2FA activo

---

#### **Cómo obtener contraseña de aplicación (si tienes 2FA):**

1. Ir a: https://account.microsoft.com/security
2. Click en "Advanced security options"
3. Click en "Add a new way to sign in or verify"
4. Seleccionar "App password"
5. Copiar la contraseña generada (16 caracteres)
6. Usar ESA contraseña en `MAIL_PASSWORD`

---

#### **Opción B: Con cuenta de servicio (RECOMENDADO para producción)**

```python
# Crear una cuenta de correo específica para el sistema
# Ejemplo: entrevistas@tuuniversidad.edu

app.config['MAIL_USERNAME'] = 'entrevistas@tuuniversidad.edu'
app.config['MAIL_PASSWORD'] = 'contraseña_de_servicio'
app.config['MAIL_DEFAULT_SENDER'] = 'Sistema de Entrevistas <entrevistas@tuuniversidad.edu>'
```

**Ventajas:**
- ✅ No usa tu cuenta personal
- ✅ Más profesional
- ✅ Puede tener contraseña simple (sin 2FA)
- ✅ Fácil de gestionar permisos

**Cómo crear:**
1. Pedir al administrador IT que cree la cuenta
2. Decir que es para "envío automatizado de emails"
3. NO activar 2FA en esa cuenta
4. Usar contraseña segura pero sin 2FA

---

### **PASO 3: Añadir imports en app.py**

```python
# Al inicio de app.py, después de los imports existentes:

from flask_mail import Mail, Message
from threading import Thread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
```

---

### **PASO 4: Inicializar Flask-Mail**

```python
# Después de la configuración de Flask-Mail (PASO 2):

mail = Mail(app)
```

---

### **PASO 5: Copiar funciones auxiliares**

Del archivo `sistema_emails_flask.py`, copiar estas funciones a `app.py`:

```python
# PARTE 2: FUNCIONES AUXILIARES
# Copiar completas:

def enviar_email_async(app, msg):
    # ...

def validar_email(email):
    # ...

def generar_email_candidato(asignacion):
    # ...

def generar_email_entrevistador(entrevistador, asignaciones):
    # ...
```

**Ubicación:** Después de las rutas existentes, antes de `if __name__ == '__main__':`

---

### **PASO 6: Copiar rutas**

Del archivo `sistema_emails_flask.py`, copiar estas rutas:

```python
# PARTE 3: RUTAS DE ENVÍO

@app.route('/admin/candidatos/enviar-emails/<semana>', methods=['POST'])
@admin_required
def enviar_emails_semana(semana):
    # ...

@app.route('/admin/candidatos/test-email', methods=['POST'])
@admin_required
def test_email():
    # ...
```

**Ubicación:** Con el resto de rutas de `/admin/candidatos/`

---

### **PASO 7: Actualizar templates**

#### **7.1 Actualizar asignaciones_semana.html**

**a) Añadir botón "Enviar Emails":**

Buscar la línea donde están los botones (Exportar, Vista Calendario) y añadir:

```html
<button class="btn btn-success me-2" onclick="mostrarModalEnviarEmails()">
    <i class="fas fa-envelope"></i> Enviar Emails
</button>
```

**b) Añadir modales:**

Al final del archivo, ANTES de `{% endblock %}`, copiar los dos modales del archivo `templates_emails_actualizaciones.html`:
- `modalEnviarEmails`
- `modalProgresoEmails`

**c) Añadir JavaScript:**

Dentro de `{% block scripts %}`, añadir las funciones:
- `mostrarModalEnviarEmails()`
- `enviarEmails()`
- `testEmail()` (opcional)

---

#### **7.2 Actualizar admin_candidatos.html (opcional)**

Añadir botón de prueba en el dashboard:

```html
<div class="card mt-4">
    <div class="card-header bg-info text-white">
        <h5><i class="fas fa-flask"></i> Pruebas</h5>
    </div>
    <div class="card-body">
        <button class="btn btn-info" onclick="testEmailConfig()">
            <i class="fas fa-paper-plane"></i> Test Email
        </button>
    </div>
</div>
```

Y añadir la función `testEmailConfig()` en el script.

---

### **PASO 8: Actualizar modelo (verificar)**

Asegurarse de que el modelo `Asignacion` tiene estos campos:

```python
class Asignacion(db.Model):
    # ... campos existentes ...
    
    enviado_email = db.Column(db.Boolean, default=False)
    fecha_envio_email = db.Column(db.DateTime, nullable=True)
```

**Si NO existen, añadir a la BD:**

```sql
ALTER TABLE asignaciones ADD COLUMN enviado_email BOOLEAN DEFAULT FALSE;
ALTER TABLE asignaciones ADD COLUMN fecha_envio_email DATETIME;
```

---

## 🧪 PRUEBAS

### **PRUEBA 1: Test de configuración**

```bash
# Terminal Python
python

>>> from app import app, mail
>>> with app.app_context():
...     from flask_mail import Message
...     msg = Message('Test', recipients=['tu_email@test.com'])
...     msg.body = 'Test básico'
...     mail.send(msg)
...     print("Email enviado!")
>>> exit()
```

**Resultado esperado:**
- ✅ "Email enviado!" sin errores
- ✅ Email llega a tu bandeja en 1-2 minutos

**Si hay error:**
- ❌ `Connection refused` → Verifica MAIL_SERVER y MAIL_PORT
- ❌ `Authentication failed` → Verifica usuario y contraseña
- ❌ `TLS error` → Verifica MAIL_USE_TLS=True

---

### **PRUEBA 2: Test desde la interfaz**

```
1. Iniciar app: python app.py
2. Login como admin
3. Ir a /admin/candidatos
4. Click en "Test Email" (si añadiste el botón)
5. Introducir tu email
6. Click "Enviar"
```

**Resultado esperado:**
```
✅ Email de prueba enviado correctamente a tu_email@test.com

Revisa tu bandeja de entrada (y spam)
```

---

### **PRUEBA 3: Limpiar y preparar datos**

```bash
# Limpiar BD
python limpiar_base_datos.py

# Seleccionar opción 1 (limpiar todo)
# Confirmar con "si"
```

---

### **PRUEBA 4: Crear datos de prueba**

```
1. Ir a la app → Crear 3 reservas:
   - Lunes 17/11/2025 09:00-09:30
   - Lunes 17/11/2025 09:30-10:00  
   - Martes 18/11/2025 10:00-10:30

2. Cargar Excel de prueba:
   - candidatos_test_semana47.xlsx
   - Semana: 46
   - Umbral: 7.0
   - Resultado: 30 candidatos importados ✅

3. Ejecutar asignación:
   - Click "Ejecutar Asignación"
   - Semana de carga: 46
   - Resultado: 6 candidatos asignados ✅
```

---

### **PRUEBA 5: Envío de emails**

```
1. Ir a "Ver Asignaciones" (Semana 46)

2. Click "Enviar Emails"

3. Seleccionar "Solo Candidatos" (para probar)

4. NO marcar "Reenviar"

5. Click "Enviar Emails"

6. Esperar... (5-10 segundos)

7. Resultado esperado:
   ✅ Emails enviados correctamente
   
   📧 Candidatos:
     • Enviados: 6
     • Errores: 0
   
   📊 Total: 6 emails enviados
```

---

### **PRUEBA 6: Verificar emails recibidos**

**a) Verificar en tu bandeja:**
- Buscar emails de los candidatos (si usaste emails reales de prueba)
- O verificar en la consola si hay prints de errores

**b) Verificar formato:**
- ✅ Email HTML bien formateado
- ✅ Fecha en español
- ✅ Hora correcta
- ✅ Datos del candidato correctos
- ✅ Logo/header con colores

**c) Verificar BD:**
```sql
SELECT 
    c.nombre,
    c.apellidos,
    a.enviado_email,
    a.fecha_envio_email
FROM asignaciones a
JOIN candidatos c ON a.candidato_id = c.id
WHERE c.semana_carga = '2024-W46';
```

**Resultado esperado:**
```
nombre  | apellidos | enviado_email | fecha_envio_email
--------|-----------|---------------|------------------
Julia   | Cruz      | 1             | 2025-11-20 10:30
Sandra  | Álvarez   | 1             | 2025-11-20 10:30
...
```

---

## 🎨 PERSONALIZACIÓN

### **Cambiar colores del email:**

En `generar_email_candidato()`, buscar:

```python
bgcolor="#4472C4"  # Azul del header
```

Cambiar por tu color corporativo:
```python
bgcolor="#FF5733"  # Naranja
bgcolor="#28A745"  # Verde
bgcolor="#6F42C1"  # Morado
```

---

### **Añadir logo institucional:**

En el HTML del email, en la sección header:

```python
html = f"""
...
<tr>
    <td bgcolor="#4472C4" style="padding: 40px 30px; text-align: center;">
        <!-- AÑADIR LOGO -->
        <img src="https://tuuniversidad.edu/logo.png" 
             alt="Logo" 
             width="150" 
             style="margin-bottom: 20px;">
        
        <h1 style="color: #ffffff;">
            📋 Confirmación de Entrevista
        </h1>
    </td>
</tr>
...
"""
```

**Nota:** El logo debe estar en una URL pública accesible.

---

### **Cambiar textos:**

Todos los textos están en las funciones:
- `generar_email_candidato()` → Email a candidatos
- `generar_email_entrevistador()` → Email a entrevistadores

Buscar y reemplazar los textos según necesites.

---

## 🔒 SEGURIDAD

### **NO subir contraseñas a Git:**

```python
# MALO ❌
app.config['MAIL_PASSWORD'] = 'mi_contraseña_123'

# BUENO ✅
import os
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
```

**Crear archivo .env:**
```bash
# .env
MAIL_USERNAME=entrevistas@tuuniversidad.edu
MAIL_PASSWORD=tu_contraseña_aqui
```

**Cargar en app.py:**
```python
from dotenv import load_dotenv
import os

load_dotenv()

app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
```

**Añadir a .gitignore:**
```
.env
*.pyc
__pycache__/
```

---

## 📊 MONITOREO

### **Ver logs de envío:**

```python
# Añadir logging en app.py

import logging

logging.basicConfig(
    filename='emails.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# En la función enviar_emails_semana:
logging.info(f"Email enviado a {candidato.email}")
logging.error(f"Error enviando a {candidato.email}: {str(e)}")
```

**Ver logs:**
```bash
tail -f emails.log
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### **Error: "Connection refused"**

```
SMTPConnectError: Connection refused
```

**Solución:**
```python
# Verificar configuración:
MAIL_SERVER = 'smtp.office365.com'  # Correcto
MAIL_PORT = 587  # Correcto
MAIL_USE_TLS = True  # Debe ser True
```

---

### **Error: "Authentication failed"**

```
SMTPAuthenticationError: Username and Password not accepted
```

**Solución:**
1. Verifica que el email es correcto
2. Verifica que la contraseña es correcta
3. Si tienes 2FA, usa contraseña de aplicación
4. Intenta iniciar sesión manual en outlook.com para verificar

---

### **Error: "Emails van a spam"**

**Solución:**
1. Usar email corporativo (@tuuniversidad.edu)
2. Configurar SPF/DKIM (pedir a IT)
3. No usar palabras spam ("GRATIS", "URGENTE")
4. Incluir enlace "darse de baja"
5. Enviar desde dominio verificado

---

### **Error: "Email no se envía pero no hay error"**

```python
# Añadir debugging:
app.config['MAIL_DEBUG'] = True
app.config['TESTING'] = False
```

Reiniciar y ver output en consola.

---

### **Los candidatos no tienen email**

```python
# Verificar en BD:
SELECT COUNT(*) FROM candidatos WHERE email IS NULL OR email = '';
```

**Si hay candidatos sin email:**
1. Añadir emails al Excel antes de cargar
2. O actualizar manualmente:
```sql
UPDATE candidatos SET email = 'email@test.com' WHERE id = 1;
```

---

## ✅ CHECKLIST FINAL

```
CONFIGURACIÓN:
□ Flask-Mail instalado
□ Configuración Office 365 en app.py
□ Mail inicializado (mail = Mail(app))
□ Contraseña correcta (o app password si 2FA)

CÓDIGO:
□ Imports añadidos
□ Funciones auxiliares copiadas
□ Rutas copiadas
□ Modelo Asignacion tiene campos enviado_email

TEMPLATES:
□ Botón "Enviar Emails" añadido
□ Modales añadidos
□ JavaScript añadido
□ Botón test añadido (opcional)

PRUEBAS:
□ Test básico funciona
□ Test desde interfaz funciona
□ BD limpia
□ Datos de prueba cargados
□ Asignación ejecutada
□ Envío de email funciona
□ Emails llegan correctamente
□ Formato HTML correcto

SEGURIDAD:
□ Contraseña NO en Git
□ .env configurado
□ .gitignore actualizado

¡TODO LISTO! ✅
```

---

## 🎉 SIGUIENTE PASO

Tu sistema de emails está listo. Ahora puedes:

1. ✅ Limpiar datos de prueba
2. ✅ Cargar candidatos reales
3. ✅ Ejecutar asignaciones
4. ✅ Enviar emails reales

**¡El sistema está completo y funcional!** 🚀

---

## 📞 AYUDA ADICIONAL

Si algo no funciona:

1. **Ver logs de error:**
   ```bash
   tail -f app.log
   ```

2. **Test manual de SMTP:**
   ```python
   python test_smtp.py
   ```

3. **Verificar configuración:**
   ```python
   print(app.config['MAIL_SERVER'])
   print(app.config['MAIL_PORT'])
   print(app.config['MAIL_USERNAME'])
   ```

4. **Contactar con IT si:**
   - No puedes conectar a smtp.office365.com
   - Necesitas cuenta de servicio
   - Necesitas configurar SPF/DKIM

---

¿Todo claro? ¡A por ello! 💪
