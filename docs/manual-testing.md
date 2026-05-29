# Manual Testing Guide — SasVault

> Guía paso a paso para probar SasVault manualmente en desarrollo.
> Útil para verificar flujos de usuario sin automatización, validar permisos, y entender cómo funciona el sistema.

---

## Prerequisitos

- Docker Compose levantado: `docker compose up -d`
- Django runserver: `cd backend && python manage.py runserver`
- (Opcional) Herramientas: Bruno, Postman, o curl desde terminal

---

## Opción A: Swagger UI (más fácil, sin instalar nada)

1. Abre `http://localhost:8000/api/docs/`
2. Verás todos los endpoints con formularios interactivos
3. Haz clic en un endpoint → se expande con botón **Try it out**
4. Primero necesitas autenticarte:
   - Usa `POST /api/v1/auth/login/` con email y password
   - Copia el `access` token de la respuesta
   - Haz clic en **Authorize** (arriba a la derecha) y pega `Bearer <token>`
5. Ya puedes probar cualquier endpoint autenticado

---

## Opción B: curl desde terminal

### Paso 0 — Crear datos de prueba

```bash
cd backend
source .venv/bin/activate

python manage.py shell -c "
from apps.organizations.services.organization_service import create_organization
from apps.authentication.services.user_service import create_user
from apps.authentication.models import UserRole

org = create_organization(name='Acme Corp')
admin = create_user(
    organization=org,
    email='admin@acme.com',
    password='Admin123!',
    role=UserRole.ORG_ADMIN,
)
viewer = create_user(
    organization=org,
    email='viewer@acme.com',
    password='Viewer123!',
    role=UserRole.VIEWER,
)
print('Org:', org.id)
print('Admin:', admin.email)
print('Viewer:', viewer.email)
"
```

Guardará dos usuarios en la BD:
- **admin@acme.com** (OrgAdmin): puede crear/editar/borrar carpetas y documentos
- **viewer@acme.com** (Viewer): solo puede leer

### Paso 1 — Login y guardar token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"Admin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

echo "Token: $TOKEN"
```

Guarda el token en una variable para las siguientes requests.

### Paso 2 — Inicializar el bucket MinIO

Necesario antes de subir documentos:

```bash
python manage.py init_storage
# → Storage bucket is ready.
```

### Paso 3 — Crear una carpeta raíz

```bash
FOLDER_ID=$(curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Contratos 2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

echo "Folder ID: $FOLDER_ID"
```

### Paso 4 — Crear una subcarpeta dentro

```bash
SUBFOLDER_ID=$(curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Enero\", \"parent_id\": \"$FOLDER_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

echo "Subfolder ID: $SUBFOLDER_ID"
```

### Paso 5 — Intentar borrar carpeta con hijos (esperado: falla)

```bash
curl -s -X DELETE "http://localhost:8000/api/v1/folders/$FOLDER_ID/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Respuesta esperada (409 Conflict):
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Cannot delete a folder that has sub-folders.",
    "details": {}
  }
}
```

### Paso 6 — Subir un documento PDF

```bash
# Crear un PDF mínimo de prueba
python3 << 'EOF'
data = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF'
open('/tmp/test.pdf','wb').write(data)
print('PDF creado en /tmp/test.pdf')
EOF

DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.pdf" \
  -F "name=contrato_enero.pdf" \
  -F "folder_id=$FOLDER_ID" \
  -F "description=Contrato de prueba" \
  -F "tags=contrato" \
  -F "tags=2026" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

echo "Document ID: $DOC_ID"
```

### Paso 7 — Intentar borrar carpeta que contiene documentos (esperado: falla)

```bash
curl -s -X DELETE "http://localhost:8000/api/v1/folders/$FOLDER_ID/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Respuesta esperada (409 Conflict):
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Cannot delete a folder that has documents.",
    "details": {}
  }
}
```

### Paso 8 — Borrar documento y carpetas (esperado: éxito)

```bash
# Borrar documento
curl -X DELETE "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN"
# Espera: 204 No Content

# Borrar subcarpeta (está vacía)
curl -X DELETE "http://localhost:8000/api/v1/folders/$SUBFOLDER_ID/" \
  -H "Authorization: Bearer $TOKEN"
# Espera: 204 No Content

# Borrar carpeta raíz (ahora está vacía)
curl -X DELETE "http://localhost:8000/api/v1/folders/$FOLDER_ID/" \
  -H "Authorization: Bearer $TOKEN"
# Espera: 204 No Content ✓
```

### Paso 9 — Verificar permisos de rol (Viewer no puede crear)

```bash
VIEWER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@acme.com","password":"Viewer123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

# Intentar crear carpeta como Viewer — esperado: 403 Forbidden
curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "No puedo crear esto"}' | python3 -m json.tool
```

Respuesta esperada:
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to perform this action",
    "details": {}
  }
}
```

### Paso 10 — Probar status de documento (draft ↔ under_review)

Primero recrea un documento:
```bash
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.pdf" \
  -F "name=contrato_status.pdf" \
  -F "folder_id=$FOLDER_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Cambiar de draft → under_review (esperado: 200 OK)
curl -s -X PATCH "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "under_review"}' | python3 -m json.tool

# Intentar cambiar de under_review → approved directamente (esperado: 400 Bad Request)
# Porque approved requiere WorkflowExecution (Fase 3.2), no está disponible en Fase 2
curl -s -X PATCH "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "approved"}' | python3 -m json.tool
```

Respuesta esperada (el serializer rechaza "approved" como opción):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": {"status": ["\"approved\" is not a valid choice. Valid choices are: draft, under_review"]}
  }
}
```

### Paso 11 — Ver los audit logs en base de datos

Los endpoints de audit logs son Fase 3, pero puedes inspeccionar los logs que se crearon:

```bash
python manage.py shell -c "
from apps.audit.models import AuditLog
print('Últimos 10 eventos de auditoría:')
print('-' * 60)
for log in AuditLog.objects.order_by('-created_at')[:10]:
    print(f'{log.action:20} {log.entity_type:12} {str(log.created_at)[-8:]}')
    print(f'  Entity: {log.entity_id}')
    if log.old_values:
        print(f'  Old: {log.old_values}')
    if log.new_values:
        print(f'  New: {log.new_values}')
    print()
"
```

---

## Paso 12 — Verificar tenant isolation (ORG A no ve datos de ORG B)

```bash
# Crear segunda organización
python manage.py shell -c "
from apps.organizations.services.organization_service import create_organization
from apps.authentication.services.user_service import create_user
from apps.authentication.models import UserRole

org_b = create_organization(name='TechCorp')
admin_b = create_user(
    organization=org_b,
    email='admin_b@techcorp.com',
    password='AdminB123!',
    role=UserRole.ORG_ADMIN,
)
print('OrgB Admin:', admin_b.email)
"

# Login como admin_b
TOKEN_B=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin_b@techcorp.com","password":"AdminB123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

# Intentar acceder al $FOLDER_ID de AcmeCorp (esperado: 404)
curl -s "http://localhost:8000/api/v1/folders/$FOLDER_ID/" \
  -H "Authorization: Bearer $TOKEN_B" | python3 -m json.tool
```

Respuesta esperada (404 NotFound):
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Folder ... not found.",
    "details": {}
  }
}
```

---

## Casos de prueba recomendados

| Caso | Comando | Resultado esperado |
|------|---------|-------------------|
| Login exitoso | POST `/auth/login/` | 200, token en respuesta |
| Crear carpeta como OrgAdmin | POST `/folders/` | 201 Created |
| Crear carpeta como Viewer | POST `/folders/` | 403 Forbidden |
| Subir documento válido (PDF) | POST `/documents/` | 201, ocr_content vacío |
| Subir documento inválido (EXE disfrazado) | POST `/documents/` (EXE) | 400, INVALID_MIME_TYPE |
| Subir documento >50MB | POST `/documents/` (>50MB) | 400, FILE_TOO_LARGE |
| Borrar carpeta con hijos | DELETE `/folders/{id}` | 409 Conflict |
| Borrar carpeta con documentos | DELETE `/folders/{id}` | 409 Conflict |
| Cambiar status draft→under_review | PATCH `/documents/{id}` | 200 OK |
| Cambiar status draft→approved | PATCH `/documents/{id}` | 400 (approved no permitido) |
| Ver documentos de otra org | GET `/documents/` (como usuario de org B) | 200, lista vacía |

---

## Debugging

### Ver todos los logs de auditoría de una organización

```bash
python manage.py shell -c "
from apps.audit.models import AuditLog
from apps.organizations.models import Organization

org = Organization.objects.first()
logs = AuditLog.objects.filter(organization=org).order_by('-created_at')
for log in logs[:20]:
    print(f'{log.created_at.strftime(\"%H:%M:%S\")} | {log.action:15} | {log.entity_type:10} | {log.user.email if log.user else \"system\":20} | {log.entity_id}')
"
```

### Ver tokens JWT decodificados

```bash
python3 << 'EOF'
import sys, json
from jwt import decode
from jwt.exceptions import DecodeError

token = input("Pega el token JWT: ").strip()
try:
    decoded = decode(token, options={"verify_signature": False})
    print(json.dumps(decoded, indent=2))
except DecodeError as e:
    print(f"Error: {e}")
EOF
```

### Verificar documentos en base de datos

```bash
python manage.py shell -c "
from apps.documents.models import Document
from apps.organizations.models import Organization

org = Organization.objects.first()
docs = Document.objects.filter(organization=org)
for doc in docs:
    print(f'{doc.name:30} | {doc.status:15} | v{doc.version} | {doc.file_size} bytes')
"
```

### Limpiar datos de prueba

```bash
python manage.py shell -c "
from apps.documents.models import Document, DocumentVersion, Folder
from apps.organizations.models import Organization

org = Organization.objects.first()
Document.objects.filter(organization=org).delete()
Folder.objects.filter(organization=org).delete()
print('Datos de prueba eliminados')
"
```
