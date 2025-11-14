# 🔧 GUÍA DE INTEGRACIÓN - GESTIÓN DE CANDIDATOS EN LA WEB

## 📋 ARCHIVOS GENERADOS

1. **rutas_candidatos.py** - Código de las rutas Flask
2. **admin_candidatos.html** - Template principal
3. **candidatos_semana.html** - Vista de candidatos (a crear)
4. **asignaciones_semana.html** - Vista de asignaciones (a crear)

---

## 🚀 PASO 1: INTEGRAR RUTAS EN APP.PY

### **1. Añadir imports al inicio de app.py:**

```python
# Después de los imports existentes
import pandas as pd
from werkzeug.utils import secure_filename
import hashlib
import os
from datetime import date
```

### **2. Configurar carpeta de uploads:**

```python
# Después de la configuración de la BD
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
```

### **3. Copiar las funciones auxiliares:**

Copia del archivo `rutas_candidatos.py`:
- `allowed_file()`
- `calcular_semana_iso()`
- `parsear_semana_iso()`
- `obtener_semanas_disponibles()`

### **4. Copiar las rutas:**

Copia estas rutas de `rutas_candidatos.py` a `app.py`:
- `@app.route('/admin/candidatos')`
- `@app.route('/admin/candidatos/cargar-excel', methods=['POST'])`
- `@app.route('/admin/candidatos/ejecutar-asignacion', methods=['POST'])`
- `@app.route('/admin/candidatos/semana/<semana>')`
- `@app.route('/admin/candidatos/asignaciones/<semana>')`

---

## 🎨 PASO 2: CREAR TEMPLATES

### **1. Copiar admin_candidatos.html:**

```bash
cp admin_candidatos.html templates/
```

### **2. Crear candidatos_semana.html:**

```html
{% extends "base.html" %}

{% block title %}Candidatos Semana {{ semana }}{% endblock %}

{% block content %}
<div class="container mt-4">
    <h2><i class="fas fa-users"></i> Candidatos - Semana {{ semana }}</h2>
    
    <div class="row mt-3">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h5>Estadísticas</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-3">
                            <strong>Total:</strong> {{ stats.total_candidatos }}
                        </div>
                        <div class="col-md-3">
                            <strong>Pendientes:</strong> {{ stats.candidatos_pendientes }}
                        </div>
                        <div class="col-md-3">
                            <strong>Asignados:</strong> {{ stats.candidatos_asignados }}
                        </div>
                        <div class="col-md-3">
                            <strong>Entrevistados:</strong> {{ stats.candidatos_entrevistados }}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row mt-3">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h5>Lista de Candidatos</h5>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Solicitud</th>
                                    <th>Nombre</th>
                                    <th>Apellidos</th>
                                    <th>Nota</th>
                                    <th>Estado</th>
                                    <th>Primera Opción</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for candidato in candidatos %}
                                <tr>
                                    <td>{{ candidato.solicitud }}</td>
                                    <td>{{ candidato.nombre }}</td>
                                    <td>{{ candidato.apellidos }}</td>
                                    <td>{{ "%.2f"|format(candidato.media_estudios) }}</td>
                                    <td>
                                        {% if candidato.estado == 'pendiente' %}
                                        <span class="badge bg-warning">Pendiente</span>
                                        {% elif candidato.estado == 'asignado' %}
                                        <span class="badge bg-success">Asignado</span>
                                        {% elif candidato.estado == 'entrevistado' %}
                                        <span class="badge bg-info">Entrevistado</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ candidato.primera_opcion[:50] }}...</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <a href="{{ url_for('admin_candidatos') }}" class="btn btn-secondary mt-3">
        <i class="fas fa-arrow-left"></i> Volver
    </a>
</div>
{% endblock %}
```

### **3. Crear asignaciones_semana.html:**

```html
{% extends "base.html" %}

{% block title %}Asignaciones Semana {{ semana }}{% endblock %}

{% block content %}
<div class="container mt-4">
    <h2><i class="fas fa-calendar-check"></i> Asignaciones - Semana {{ semana }}</h2>
    
    <div class="row mt-3">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h5>Lista de Asignaciones</h5>
                </div>
                <div class="card-body">
                    {% if asignaciones %}
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Candidato</th>
                                    <th>Nota</th>
                                    <th>Fecha</th>
                                    <th>Hora Inicio</th>
                                    <th>Posición</th>
                                    <th>Hora Exacta</th>
                                    <th>Entrevistador</th>
                                    <th>Estado</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for asignacion in asignaciones %}
                                <tr>
                                    <td>{{ asignacion.candidato.nombre }} {{ asignacion.candidato.apellidos }}</td>
                                    <td>{{ "%.2f"|format(asignacion.candidato.media_estudios) }}</td>
                                    <td>{{ asignacion.reserva.fecha.strftime('%d/%m/%Y') }}</td>
                                    <td>{{ asignacion.reserva.hora_inicio.strftime('%H:%M') }}</td>
                                    <td>{{ asignacion.posicion }}</td>
                                    <td>{{ asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else '-' }}</td>
                                    <td>{{ asignacion.entrevistador.username }}</td>
                                    <td>
                                        <span class="badge bg-success">{{ asignacion.estado }}</span>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    {% else %}
                    <p class="text-muted">No hay asignaciones para esta semana.</p>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <a href="{{ url_for('admin_candidatos') }}" class="btn btn-secondary mt-3">
        <i class="fas fa-arrow-left"></i> Volver
    </a>
</div>
{% endblock %}
```

---

## 🔗 PASO 3: AÑADIR ENLACE EN MENÚ

Añadir en la barra de navegación del template base (solo para admins):

```html
{% if es_admin %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('admin_candidatos') }}">
        <i class="fas fa-users"></i> Candidatos
    </a>
</li>
{% endif %}
```

O si usas un menú dropdown:

```html
{% if es_admin %}
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="navbarDropdown" role="button" data-bs-toggle="dropdown">
        Administración
    </a>
    <ul class="dropdown-menu">
        <li><a class="dropdown-item" href="{{ url_for('admin_usuarios') }}">Usuarios</a></li>
        <li><a class="dropdown-item" href="{{ url_for('admin_estadisticas') }}">Estadísticas</a></li>
        <li><a class="dropdown-item" href="{{ url_for('todas_reservas') }}">Todas las Reservas</a></li>
        <li><hr class="dropdown-divider"></li>
        <li><a class="dropdown-item" href="{{ url_for('admin_candidatos') }}">
            <i class="fas fa-users"></i> Candidatos
        </a></li>
    </ul>
</li>
{% endif %}
```

---

## ✅ PASO 4: VERIFICAR DEPENDENCIAS

Asegúrate de tener instalado:

```bash
pip install pandas openpyxl werkzeug
```

---

## 🧪 PASO 5: PROBAR LA INTEGRACIÓN

### **1. Iniciar la aplicación:**
```bash
python app.py
```

### **2. Acceder como admin:**
```
http://localhost:5000/login
Usuario: admin
Contraseña: admin123
```

### **3. Ir a Candidatos:**
```
http://localhost:5000/admin/candidatos
```

### **4. Probar carga de Excel:**
- Selecciona archivo
- Elige semana
- Define umbral
- Click "Cargar y Procesar"

### **5. Probar asignación:**
- Selecciona semana de carga
- Define límite por profesor (opcional)
- Click "Ejecutar Asignación"

---

## 📊 FUNCIONALIDADES IMPLEMENTADAS

### **✅ Cargar Excel:**
- Selector visual de semanas
- Umbral de nota configurable
- Validación de duplicados
- Procesamiento automático
- Feedback en tiempo real

### **✅ Asignación Automática:**
- Selector de semana de carga
- Cálculo automático de semana de entrevistas
- Límite por profesor opcional
- Confirmación antes de ejecutar
- Resultados detallados

### **✅ Visualización:**
- Estadísticas generales
- Candidatos por semana
- Asignaciones por semana
- Historial de cargas
- Historial de asignaciones

---

## 🎨 CARACTERÍSTICAS VISUALES

### **Selector de Semanas:**
```
Semana 45 (04/11 - 08/11)  ← Formato amigable
Semana 46 (11/11 - 15/11)  ← No necesitas saber el número ISO
Semana 47 (18/11 - 22/11)
```

### **Feedback Visual:**
- ✅ Alertas de éxito (verde)
- ❌ Alertas de error (rojo)
- ⚠️ Alertas de advertencia (amarillo)
- ℹ️ Alertas de información (azul)

### **Loading States:**
- Botones deshabilitados durante procesamiento
- Spinners de carga
- Recarga automática después del éxito

---

## 🔐 SEGURIDAD

### **Protecciones implementadas:**
- `@admin_required` en todas las rutas
- Validación de tipos de archivo
- `secure_filename()` para nombres
- Detección de duplicados por hash
- Validación de datos de entrada

---

## 📝 EJEMPLO DE USO COMPLETO

### **Lunes (Semana 45):**
1. Admin accede a `/admin/candidatos`
2. Sube archivo Excel
3. Selecciona "Semana 45 (04/11 - 08/11)"
4. Define umbral 7.0
5. Click "Cargar y Procesar"
6. ✅ 5 candidatos importados

### **Martes-Miércoles:**
Profesores reservan franjas para semana 46 en la app normal

### **Jueves:**
1. Admin va a `/admin/candidatos`
2. Sección "Asignación Automática"
3. Selecciona "Semana 45 (04/11 - 08/11)"
4. Define límite: 10 por profesor
5. Click "Ejecutar Asignación"
6. ✅ 5 candidatos asignados a W46

### **Verificar:**
1. Click "Ver Candidatos" en semana 45
2. Click "Ver Asignaciones" en semana 45
3. Todos los candidatos aparecen como "Asignado"

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### **Error: "No module named 'pandas'"**
```bash
pip install pandas openpyxl
```

### **Error: "UPLOAD_FOLDER not found"**
La carpeta se crea automáticamente, pero verifica permisos:
```bash
mkdir uploads
chmod 755 uploads
```

### **Error: "No hay candidatos pendientes"**
Verifica que la semana seleccionada tenga candidatos:
```sql
SELECT semana_carga, COUNT(*) FROM candidatos GROUP BY semana_carga;
```

### **Error: "No hay reservas disponibles"**
Los profesores deben crear reservas para la semana siguiente:
```sql
SELECT fecha, COUNT(*) FROM reservas GROUP BY fecha ORDER BY fecha;
```

---

## ✅ CHECKLIST DE INTEGRACIÓN

- [ ] Imports añadidos en app.py
- [ ] Configuración UPLOAD_FOLDER añadida
- [ ] Funciones auxiliares copiadas
- [ ] Rutas copiadas a app.py
- [ ] admin_candidatos.html en templates/
- [ ] candidatos_semana.html en templates/
- [ ] asignaciones_semana.html en templates/
- [ ] Enlace añadido en menú de navegación
- [ ] Dependencias instaladas (pandas, openpyxl)
- [ ] Carpeta uploads/ creada
- [ ] Probado cargar Excel
- [ ] Probado ejecutar asignación
- [ ] Verificado en BD

---

## 🎉 RESULTADO FINAL

Una interfaz web completa donde los administradores pueden:
1. ✅ Cargar archivos Excel con selector visual de semanas
2. ✅ Ejecutar asignaciones automáticas
3. ✅ Ver candidatos y asignaciones por semana
4. ✅ Revisar historial completo
5. ✅ Todo sin necesidad de usar el terminal

---

¿Listo para integrar? ¡Sigue los pasos y tendrás todo funcionando! 🚀
