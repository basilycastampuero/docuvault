# SasVault — Guía de desarrollo local

Referencia rápida para levantar el proyecto y probar todos los roles sin necesidad de crear datos adicionales.

## Levantar el entorno

```bash
# 1. Infraestructura (PostgreSQL 16, Redis 7, MinIO)
docker compose up -d

# 2. Backend
cd backend
source .venv/bin/activate
python manage.py runserver

# 3. Frontend (terminal aparte)
cd frontend
npm run dev
```

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/v1/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| MinIO Console | http://localhost:9001 |

Health check rápido:
```bash
curl http://localhost:8000/api/v1/health/
# → {"status":"ok","components":{"database":"ok","redis":"ok","storage":"ok"}}
```

---

## Cuentas de prueba

Todas las cuentas usan la misma contraseña: **`testpass123`**

### Organización: Acme Corp

Usa estas cuentas para probar el flujo principal. Todas pertenecen a la misma organización, lo que permite verificar el aislamiento de tenant y las diferencias de permisos entre roles.

| Email | Rol | Qué puede hacer |
|-------|-----|-----------------|
| `admin@acme.com` | `org_admin` | Todo dentro de Acme Corp: gestionar usuarios, crear workflows, ver audit logs, subir documentos |
| `supervisor@acme.com` | `supervisor` | Crear y gestionar workflows, aprobar/rechazar pasos, ver documentos |
| `editor@acme.com` | `editor` | Crear carpetas, subir documentos, iniciar ejecuciones de workflow |
| `viewer@acme.com` | `viewer` | Solo lectura: ver documentos, carpetas, workflows. Sin escritura |
| `auditor@acme.com` | `auditor` | Acceso de solo lectura al audit log. Sin acceso a documentos ni workflows |

### Organización: TechCorp

Cuenta adicional para demostrar el **aislamiento multi-tenant**: un usuario de TechCorp no puede ver ni acceder a los datos de Acme Corp, aunque use el mismo servidor.

| Email | Rol | Organización |
|-------|-----|--------------|
| `admin@techcorp.com` | `org_admin` | TechCorp |

### Nota sobre `super_admin`

El rol `super_admin` es un rol de plataforma global y **no pertenece a ningún tenant**. Recibirá `403 PERMISSION_DENIED` en todos los endpoints de dominio (`/documents/`, `/folders/`, `/workflows/`, etc.) — este es el comportamiento correcto y esperado. El acceso de super_admin es vía Django Admin (`/admin/`), no vía la API REST.

---

## Matriz de permisos por endpoint

| Endpoint | org_admin | supervisor | editor | viewer | auditor |
|----------|:---------:|:----------:|:------:|:------:|:-------:|
| GET `/documents/` | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST `/documents/` (subir) | ✅ | ✅ | ✅ | ❌ | ❌ |
| DELETE `/documents/{id}/` | ✅ | ❌ | ❌ | ❌ | ❌ |
| GET `/folders/` | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST `/folders/` | ✅ | ✅ | ✅ | ❌ | ❌ |
| GET `/workflows/templates/` | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST `/workflows/templates/` | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST `/workflows/executions/` | ✅ | ✅ | ✅ | ❌ | ❌ |
| POST `/workflows/executions/{id}/advance/` | ✅ | ✅ | ✅* | ❌ | ❌ |
| GET `/audit-logs/` | ✅ | ❌ | ❌ | ❌ | ✅ |
| GET `/search/` | ✅ | ✅ | ✅ | ✅ | ❌ |

*El editor solo puede avanzar pasos cuyo `required_role` sea `editor`.

---

## Flujos de prueba sugeridos

### 1. Flujo completo de documento (como `editor@acme.com`)
1. Login en http://localhost:5173
2. Ir a **Documentos** → subir cualquier PDF o imagen
3. Ver el badge OCR cambiar de `Pendiente` → `Procesando` → `Completado` (requiere Celery corriendo)
4. Ir a **Búsqueda** y buscar texto del documento

### 2. Flujo de workflow (como `admin@acme.com` + `editor@acme.com`)
1. Como `admin@acme.com`: ir a **Workflows → Plantillas** → crear una plantilla con al menos un paso
2. Como `editor@acme.com`: ir a un documento → iniciar ejecución del workflow
3. Como `supervisor@acme.com` o `admin@acme.com`: aprobar/rechazar el paso

### 3. Verificar aislamiento de tenant
1. Login como `admin@acme.com` → crear una carpeta o documento
2. Logout → login como `admin@techcorp.com`
3. Verificar que **no aparece** la carpeta/documento de Acme Corp

### 4. Verificar permisos de auditor
1. Login como `auditor@acme.com`
2. Verificar acceso a `/audit-logs/`
3. Verificar que **no** puede acceder a `/documents/` ni `/folders/`

---

## Correr Celery (OCR y notificaciones)

Sin Celery corriendo, las tareas asíncronas (OCR, análisis IA, notificaciones) quedan en estado `Pendiente` indefinidamente.

```bash
cd backend
source .venv/bin/activate

# Worker (procesa tareas)
celery -A config.celery worker --loglevel=info

# Beat (tareas periódicas: limpieza de blobs huérfanos a las 03:00 UTC)
celery -A config.celery beat --loglevel=info
```

---

## Recrear las contraseñas de seed

Si se perdieron las contraseñas (por ejemplo tras un `flush` de la BD):

```bash
cd backend && source .venv/bin/activate
python manage.py shell -c "
from apps.authentication.models import User
emails = [
    'admin@acme.com', 'supervisor@acme.com', 'editor@acme.com',
    'viewer@acme.com', 'auditor@acme.com', 'admin@techcorp.com',
]
for email in emails:
    u = User.objects.get(email=email)
    u.set_password('testpass123')
    u.save()
    print(f'Reset: {u.role} - {u.email}')
"
```
