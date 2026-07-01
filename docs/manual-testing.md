# Guía de Pruebas Manuales — SasVault Backend

> Referencia estructurada para verificar que cada pieza del stack está operativa.
> Organizada de menor a mayor complejidad: primero infraestructura, después lógica de negocio.
> El documento es autosuficiente: puede seguirse de principio a fin en un entorno limpio.

---

## Prerrequisitos

Antes de empezar, verificar que los siguientes procesos están corriendo:

| Proceso | Comando para levantar | Puerto |
|---|---|---|
| PostgreSQL 16 | `docker compose up -d` | 5432 |
| Redis 7 | `docker compose up -d` | 6379 |
| MinIO | `docker compose up -d` | 9000 (API), 9001 (consola) |
| Django | `source backend/.venv/bin/activate && cd backend && python manage.py runserver` | 8000 |
| Celery worker | `celery -A config.celery worker --loglevel=info` (terminal separada) | — |
| Celery beat | `celery -A config.celery beat --loglevel=info` (terminal separada, solo para cleanup) | — |

Verificar estado de contenedores:

```bash
docker compose ps
```

Salida esperada: todos los servicios en estado `healthy` o `running`.

**Nota:** si Django falla al arrancar con `connection refused` en `localhost:5432`, la infra Docker no está levantada. No es un fallo de código.

---

## Setup inicial

Este bloque solo se ejecuta una vez por entorno limpio. Crea el superusuario del sistema y el bucket de MinIO.

### Crear superusuario

El superusuario de Django tiene `role=super_admin` y puede crear organizaciones. Se crea fuera del flujo normal de la API porque la API no permite crear `super_admin`.

```bash
cd /home/basily/projects/SasVault/backend
source .venv/bin/activate
python manage.py createsuperuser
```

El comando pedirá email y password interactivamente. Para pruebas usar:
- Email: `superadmin@sasvault.dev`
- Password: `SuperAdmin123!`

### Inicializar bucket MinIO

Necesario antes de cualquier operación con archivos. El comando crea el bucket si no existe.

```bash
python manage.py init_storage
# Salida esperada: Storage bucket is ready.
```

Si falla con error de conexión: MinIO no está corriendo. Revisar `docker compose ps`.

---

## Nivel 1: Infraestructura

Verificar que cada servicio responde directamente, sin pasar por Django.

### PostgreSQL

```bash
# Conectar y ejecutar query trivial
PGPASSWORD=saasvault_pass_local psql \
  -h localhost -U saasvault_user -d saasvault_db \
  -c "SELECT version();"
```

Salida esperada: línea con `PostgreSQL 16.x`.

```bash
# Ver tablas del proyecto (deben existir si las migraciones están aplicadas)
PGPASSWORD=saasvault_pass_local psql \
  -h localhost -U saasvault_user -d saasvault_db \
  -c "\dt"
```

Salida esperada: tablas como `organizations`, `users`, `documents`, `folders`, `audit_logs`, `workflow_templates`, etc.

### Redis

> `redis-cli` requiere el paquete `redis-tools` (no viene preinstalado en Ubuntu/WSL2):
> ```bash
> sudo apt-get install -y redis-tools
> ```

```bash
redis-cli ping
# Esperado: PONG

redis-cli info server | grep redis_version
# Esperado: redis_version:7.x.x
```

### MinIO

Consola web: `http://localhost:9001` (usuario: `minioadmin`, contraseña: `minioadmin`).

Desde terminal usando el cliente mc (si está instalado):

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
mc ls local/
# Esperado: listar el bucket saasvault-documents (si init_storage ya corrió)
```

Alternativa sin mc — verificar via curl:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live
# Esperado: 200
```

---

## Nivel 2: API base

### Health check (sin autenticación)

El endpoint de health es público. No requiere token. No sigue el envelope `{data, meta}` estándar — por diseño, para compatibilidad con health checkers externos.

```bash
curl -s http://localhost:8000/api/v1/health/ | python3 -m json.tool
```

Respuesta esperada cuando todo está sano:

```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  }
}
```

Si algún componente falla, el campo correspondiente muestra `"error"` y el `status` general muestra `"degraded"`. El HTTP status code cambia a 503.

### Swagger UI y schema OpenAPI

Abrir en el navegador:

- Swagger UI interactivo: `http://localhost:8000/api/docs/`
- Redoc: `http://localhost:8000/api/redoc/`
- Schema JSON crudo: `http://localhost:8000/api/schema/`

En Swagger UI se puede autenticar pulsando el botón **Authorize** (arriba a la derecha) y pegando `Bearer <token>` para luego usar **Try it out** en cualquier endpoint.

Para descargar el schema como archivo:

```bash
curl -s http://localhost:8000/api/schema/ -o openapi.yml
# Verificar que el archivo es YAML válido y tiene contenido
head -5 openapi.yml
```

### Login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@sasvault.dev","password":"SuperAdmin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

echo "Access token: $TOKEN"
```

Respuesta completa del login (estructura):

```json
{
  "data": {
    "access": "<jwt_access_token>",
    "refresh": "<jwt_refresh_token>",
    "user": {
      "id": "...",
      "email": "superadmin@sasvault.dev",
      "role": "super_admin",
      "organization_id": null,
      "first_name": "",
      "last_name": ""
    }
  },
  "meta": {}
}
```

**Nota:** el superusuario tiene `organization_id: null` porque no pertenece a ninguna organización de negocio.

### Verificar claims del JWT

Decodificar el token (sin verificar firma — solo para inspección):

```bash
python3 << 'EOF'
import sys, base64, json

token = input("Pega el access token: ").strip()
payload_b64 = token.split(".")[1]
# Agregar padding si falta
payload_b64 += "=" * (4 - len(payload_b64) % 4)
payload = json.loads(base64.b64decode(payload_b64))
print(json.dumps(payload, indent=2))
EOF
```

Campos esperados en el payload:
- `user_id`: UUID del usuario
- `organization_id`: UUID de la organización (null para super_admin)
- `role`: string del rol (`super_admin`, `org_admin`, etc.)
- `email`: email del usuario
- `exp`: timestamp de expiración

### /auth/me/

```bash
curl -s http://localhost:8000/api/v1/auth/me/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Respuesta esperada: objeto del usuario autenticado bajo `data`.

### Refresh de token

```bash
REFRESH=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@sasvault.dev","password":"SuperAdmin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['refresh'])")

# Obtener nuevo access token usando el refresh
curl -s -X POST http://localhost:8000/api/v1/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\":\"$REFRESH\"}" | python3 -m json.tool
```

Respuesta esperada: `{"data": {"access": "<nuevo_token>"}, "meta": {}}`.

### Logout y blacklist

El JWT blacklist garantiza que el token de refresh quede inválido después del logout.

```bash
# Guardar refresh token
REFRESH=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@sasvault.dev","password":"SuperAdmin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['refresh'])")

# Hacer logout (envía el refresh al blacklist)
curl -s -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"refresh\":\"$REFRESH\"}"

# Esperado: 204 No Content

# Intentar usar el refresh después del logout — esperado: 401
curl -s -X POST http://localhost:8000/api/v1/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\":\"$REFRESH\"}" | python3 -m json.tool
```

Respuesta esperada tras logout:

```json
{
  "error": {
    "code": "token_not_valid",
    "message": "Token is blacklisted"
  }
}
```

### Request sin token (esperado: 401)

```bash
curl -s http://localhost:8000/api/v1/auth/me/ | python3 -m json.tool
# Esperado: 401 con mensaje de autenticación requerida
```

---

## Nivel 3: Multi-tenancy y RBAC

### Crear organizaciones y usuarios de prueba

Este bloque crea dos organizaciones completamente aisladas y varios usuarios con distintos roles.

```bash
# Re-autenticar como superadmin si el token expiró
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@sasvault.dev","password":"SuperAdmin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

# Crear organización A — Acme Corp
ORG_A_ID=$(curl -s -X POST http://localhost:8000/api/v1/organizations/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Org A: $ORG_A_ID"

# Crear organización B — TechCorp
ORG_B_ID=$(curl -s -X POST http://localhost:8000/api/v1/organizations/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"TechCorp"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Org B: $ORG_B_ID"
```

Ahora crear usuarios dentro de cada organización usando el shell de Django (la API de usuarios requiere estar autenticado como miembro de la org, y el superadmin no tiene org):

```bash
python manage.py shell -c "
from apps.organizations.models import Organization
from apps.authentication.services.user_service import create_user
from apps.authentication.models import UserRole

org_a = Organization.objects.get(slug='acme-corp')
org_b = Organization.objects.get(slug='techcorp')

# Org A: admin + editor + viewer + supervisor + auditor
admin_a = create_user(org_a, 'admin@acme.com', UserRole.ORG_ADMIN, password='Admin123!')
editor_a = create_user(org_a, 'editor@acme.com', UserRole.EDITOR, password='Editor123!')
viewer_a = create_user(org_a, 'viewer@acme.com', UserRole.VIEWER, password='Viewer123!')
supervisor_a = create_user(org_a, 'supervisor@acme.com', UserRole.SUPERVISOR, password='Supervisor123!')
auditor_a = create_user(org_a, 'auditor@acme.com', UserRole.AUDITOR, password='Auditor123!')

# Org B: solo admin
admin_b = create_user(org_b, 'admin@techcorp.com', UserRole.ORG_ADMIN, password='AdminB123!')

print('Usuarios creados OK')
print('Org A:', org_a.id)
print('Org B:', org_b.id)
"
```

### Login como admin de Org A

```bash
TOKEN_A=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"Admin123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

TOKEN_VIEWER=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@acme.com","password":"Viewer123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

TOKEN_EDITOR=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"editor@acme.com","password":"Editor123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

TOKEN_SUPERVISOR=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"supervisor@acme.com","password":"Supervisor123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

TOKEN_AUDITOR=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"auditor@acme.com","password":"Auditor123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")

TOKEN_B=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techcorp.com","password":"AdminB123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access'])")
```

### Verificar aislamiento de tenant

Crear una carpeta como admin de Org A, luego intentar verla como admin de Org B:

```bash
# Admin A crea carpeta
FOLDER_A_ID=$(curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"name":"Carpeta de Acme"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Carpeta Org A: $FOLDER_A_ID"

# Admin B intenta acceder a esa carpeta — esperado: 404 (no ve datos de otra org)
curl -s "http://localhost:8000/api/v1/folders/$FOLDER_A_ID/" \
  -H "Authorization: Bearer $TOKEN_B" | python3 -m json.tool
```

Respuesta esperada:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "..."
  }
}
```

La razón es que el selector siempre filtra por `organization`. Desde la perspectiva de Org B, esa carpeta simplemente no existe.

### Verificar RBAC: Viewer no puede crear

```bash
# Viewer intenta crear carpeta — esperado: 403
curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $TOKEN_VIEWER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Intento de viewer"}' | python3 -m json.tool
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

### Listar usuarios de la organización

```bash
# Admin A ve los usuarios de su org
curl -s http://localhost:8000/api/v1/users/ \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: lista de los 5 usuarios de Acme, ninguno de TechCorp
```

---

## Nivel 4: Gestión documental
# Aqui me quedé en la ultima sesion 10/06 -V
### Crear jerarquía de carpetas

```bash
# Carpeta raíz (ya existe $FOLDER_A_ID del nivel anterior)
# Crear subcarpeta
SUBFOLDER_ID=$(curl -s -X POST http://localhost:8000/api/v1/folders/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Enero 2026\", \"parent_id\":\"$FOLDER_A_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Subcarpeta: $SUBFOLDER_ID"

# Listar hijos de la carpeta raíz
curl -s "http://localhost:8000/api/v1/folders/$FOLDER_A_ID/children/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: lista con "Enero 2026"
```

### Intentar borrar carpeta con hijos (esperado: 409)

```bash
curl -s -X DELETE "http://localhost:8000/api/v1/folders/$FOLDER_A_ID/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

Respuesta esperada:

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Cannot delete a folder that has sub-folders.",
    "details": {}
  }
}
```

### Subir un documento PDF real a MinIO

Crear un PDF mínimo válido:

```bash
python3 << 'EOF'
content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF"""
open('/tmp/contrato.pdf','wb').write(content)
print('PDF creado en /tmp/contrato.pdf')
EOF
```

Subir el documento:

```bash
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/contrato.pdf" \
  -F "name=contrato_enero.pdf" \
  -F "folder_id=$SUBFOLDER_ID" \
  -F "description=Contrato de prueba Enero 2026" \
  -F "tags=contrato" \
  -F "tags=2026" \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['id'])")
echo "Document ID: $DOC_ID"
```

Verificar el documento recién creado:

```bash
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

Campos importantes a verificar en la respuesta:
- `status`: debe ser `"draft"`
- `ocr_status`: debe ser `"pending"` (si el worker está corriendo, cambiará pronto)
- `file_size`: tamaño en bytes del archivo
- `checksum`: SHA-256 del archivo
- `storage_path`: ruta del blob en MinIO

### Verificar el blob en MinIO

Después del upload, ir a la consola de MinIO en `http://localhost:9001` y navegar al bucket `saasvault-documents`. Debe aparecer el archivo con la ruta que coincide con `storage_path` de la respuesta anterior.

### Obtener URL de descarga (presigned URL)

```bash
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/download/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

Respuesta esperada:

```json
{
  "data": {
    "url": "http://localhost:9000/saasvault-documents/...?X-Amz-Signature=..."
  },
  "meta": {}
}
```

Descargar el archivo usando esa URL:

```bash
PRESIGNED_URL=$(curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/download/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['url'])")

curl -s "$PRESIGNED_URL" -o /tmp/descargado.pdf
file /tmp/descargado.pdf
# Esperado: PDF document
```

### Detectar MIME real (python-magic)

Subir un archivo que no es lo que dice ser (EXE disfrazado de .pdf):

```bash
# Crear un ejecutable falso (magic bytes de Windows PE: MZ)
python3 -c "open('/tmp/malware.pdf','wb').write(b'MZ' + b'\x00'*100)"

curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/malware.pdf" \
  -F "name=virus.pdf" \
  -F "folder_id=$SUBFOLDER_ID" | python3 -m json.tool
```

Respuesta esperada (400):

```json
{
  "error": {
    "code": "INVALID_MIME_TYPE",
    "message": "File type application/x-dosexec is not allowed.",
    "details": {}
  }
}
```

La detección usa `python-magic` que lee los magic bytes reales del archivo, no la extensión ni el Content-Type declarado.

### Subir nueva versión de un documento

```bash
# Crear PDF ligeramente modificado para simular revisión
python3 -c "open('/tmp/contrato_v2.pdf','wb').write(b'%PDF-1.4\nVersion 2 content\n%%EOF')"

curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/versions/" \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/contrato_v2.pdf" \
  | python3 -m json.tool
# Esperado: 201, version_number: 2

# Listar versiones
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/versions/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: lista con 2 versiones, version_number 1 y 2
```

### Soft delete — el documento desaparece de la lista pero no de la DB

```bash
# Borrar el documento
curl -s -X DELETE "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A"
# Esperado: 204 No Content

# Verificar que ya no aparece en el listado
curl -s http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: lista sin ese documento

# Pero existe en la base de datos con deleted_at poblado
python manage.py shell -c "
from apps.documents.models import Document
import uuid
doc = Document.all_objects.get(id='$DOC_ID')
print('deleted_at:', doc.deleted_at)
print('storage_path:', doc.storage_path)
print('El blob en MinIO todavia existe — cleanup lo eliminara despues')
"
```

**Nota:** el blob en MinIO no se elimina en el soft delete. Lo hace `cleanup_orphan_blobs` (ver Nivel 9).

### Limpiar y recrear para continuar los niveles siguientes

Para los niveles 5 en adelante necesitamos un documento activo con OCR:

```bash
# Recrear documento PDF
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/contrato.pdf" \
  -F "name=contrato_ocr.pdf" \
  -F "folder_id=$SUBFOLDER_ID" \
  -F "description=Documento para prueba de OCR y busqueda" \
  -F "tags=contrato" \
  -F "tags=prueba" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Nuevo DOC_ID: $DOC_ID"
```

---

## Nivel 5: Pipeline OCR

El OCR se ejecuta de forma asíncrona mediante Celery. El worker debe estar corriendo.

### Verificar que el worker está vivo

```bash
# En la terminal donde corre el worker deberías ver:
# [celery@hostname] ready.
# Si no, lanzarlo:
# celery -A config.celery worker --loglevel=info

# Verificar workers activos mediante Celery inspect
celery -A config.celery inspect active
# Si hay workers: muestra su estado. Si no hay: "Error: No nodes replied..."
```

### Observar el ocr_status en tiempo real

Tras subir un PDF, el campo `ocr_status` pasa por:
`pending` → `processing` → `completed` (o `failed`/`skipped`)

```bash
# Verificar estado actual (puede seguir en pending si el worker es lento)
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('ocr_status:', d['ocr_status'], '| ocr_content:', d.get('ocr_content','')[:80])"
```

**Nota sobre el PDF mínimo de prueba:** el PDF que creamos en el Nivel 4 es un esqueleto válido pero sin texto real. Tesseract lo procesará (`ocr_status = completed`) pero `ocr_content` puede quedar vacío. Para probar OCR real con texto extraíble, usar una imagen PNG con texto:

```bash
# Crear imagen PNG con texto (requiere Python Pillow)
python3 << 'EOF'
try:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (400, 100), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "Contrato de prueba SasVault 2026", fill='black')
    img.save('/tmp/doc_texto.png')
    print("Imagen creada en /tmp/doc_texto.png")
except ImportError:
    print("Pillow no instalado. Usar un PDF o imagen real con texto para OCR.")
EOF

# Subir la imagen
DOC_IMG_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/doc_texto.png" \
  -F "name=imagen_con_texto.png" \
  -F "folder_id=$SUBFOLDER_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Doc imagen: $DOC_IMG_ID"
```

Esperar unos segundos y verificar:

```bash
curl -s "http://localhost:8000/api/v1/documents/$DOC_IMG_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print('ocr_status:', d['ocr_status'])
print('ocr_content:', d.get('ocr_content', '(vacio)')[:200])
"
```

Resultado esperado si Tesseract está instalado (`apt install tesseract-ocr tesseract-ocr-spa`):
- `ocr_status: "completed"`
- `ocr_content`: texto extraído de la imagen

Si Tesseract no está instalado, el worker fallará y `ocr_status` será `"failed"`.

### Verificar tipos de archivo que saltean OCR

Los archivos Office (`.docx`, `.xlsx`, `.zip`) no pasan por OCR — Tesseract no los soporta. El sistema los marca como `skipped`:

```bash
# Crear un docx falso (la validación MIME verificará los bytes reales)
# Para una prueba real usar un archivo .docx genuino.
# Con el mime type correcto (ZIP + estructura Office):
python3 -c "
import zipfile, io
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as z:
    z.writestr('[Content_Types].xml', '<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"></Types>')
buf.seek(0)
open('/tmp/documento.docx','wb').write(buf.read())
print('docx creado')
"

DOC_DOCX_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/documento.docx" \
  -F "name=hoja_de_calculo.docx" \
  -F "folder_id=$SUBFOLDER_ID" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('id','ERROR:'+str(d)))")

# Esperar y verificar
sleep 3
curl -s "http://localhost:8000/api/v1/documents/$DOC_DOCX_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('ocr_status:', d['ocr_status'])"
# Esperado: "skipped"
```

### Forzar reprocessado OCR

```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_IMG_ID/reprocess-ocr/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: 202 Accepted — {"data": {"message": "OCR reprocessing queued."}, "meta": {}}
```

### Ver logs del worker mientras procesa

En la terminal del Celery worker deberías ver líneas como:

```
[INFO/ForkPoolWorker] Task apps.documents.tasks.document_tasks.process_ocr[<uuid>] received
[INFO/ForkPoolWorker] Task apps.documents.tasks.document_tasks.process_ocr[<uuid>] succeeded
```

---

## Nivel 6: Full-Text Search

El FTS de PostgreSQL se alimenta automáticamente: cuando `ocr_content` se guarda, un signal `post_save` reconstruye `search_vector`. Para buscar por contenido, el documento debe tener `ocr_status = completed` y `ocr_content` no vacío.

### Buscar por nombre

```bash
# El nombre del documento también se indexa (peso A — máxima relevancia)
curl -s "http://localhost:8000/api/v1/search/?q=contrato" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

Respuesta esperada: lista de documentos que contienen "contrato" en nombre, descripción o tags, bajo `data`, con `meta.count`.

### Buscar por contenido OCR

```bash
# Buscar por texto que aparece en el ocr_content del documento de imagen
curl -s "http://localhost:8000/api/v1/search/?q=SasVault+2026" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: el documento imagen_con_texto.png aparece en los resultados
```

### Filtros adicionales

```bash
# Filtrar por carpeta
curl -s "http://localhost:8000/api/v1/search/?q=contrato&folder=$SUBFOLDER_ID" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool

# Filtrar por status
curl -s "http://localhost:8000/api/v1/search/?q=contrato&status=draft" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

### El FTS respeta aislamiento de tenant

```bash
# Admin B busca "contrato" — debe obtener lista vacía (no ve datos de Org A)
curl -s "http://localhost:8000/api/v1/search/?q=contrato" \
  -H "Authorization: Bearer $TOKEN_B" | python3 -m json.tool
# Esperado: data: [], meta.count: 0
```

---

## Nivel 7: Workflows

El motor de workflows permite definir flujos de aprobación con pasos y roles requeridos. Al iniciar una ejecución, el documento pasa a `under_review`. Al aprobar el paso final, el documento pasa a `approved`.

### Crear un template de workflow

El template define la estructura (pasos). Lo crea el `org_admin`.

```bash
TEMPLATE_ID=$(curl -s -X POST http://localhost:8000/api/v1/workflows/templates/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aprobacion de Contratos",
    "description": "Flujo de revision y aprobacion de contratos",
    "steps": [
      {
        "name": "Revision inicial",
        "order": 1,
        "required_role": "supervisor",
        "is_final": false
      },
      {
        "name": "Aprobacion final",
        "order": 2,
        "required_role": "org_admin",
        "is_final": true
      }
    ]
  }' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Template: $TEMPLATE_ID"
```

### Listar templates

```bash
curl -s http://localhost:8000/api/v1/workflows/templates/ \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

### Iniciar ejecución (start workflow)

El documento debe estar en status `draft`. Iniciar la ejecución lo mueve a `under_review`.

```bash
EXEC_ID=$(curl -s -X POST http://localhost:8000/api/v1/workflows/executions/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": \"$DOC_ID\",
    \"template_id\": \"$TEMPLATE_ID\"
  }" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('id','ERROR:'+str(d)))")
echo "Execution: $EXEC_ID"

# Verificar que el documento ahora está en under_review
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; print('status:', json.load(sys.stdin)['data']['status'])"
# Esperado: "under_review"
```

### Intentar iniciar una segunda ejecución (esperado: 409)

```bash
curl -s -X POST http://localhost:8000/api/v1/workflows/executions/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\":\"$DOC_ID\",\"template_id\":\"$TEMPLATE_ID\"}" | python3 -m json.tool
# Esperado: 409 WORKFLOW_ALREADY_ACTIVE
```

### Avanzar el paso 1 — Supervisor aprueba

El paso 1 requiere rol `supervisor`. Intentar avanzarlo con el admin (puede por override) o con el supervisor:

```bash
# Avanzar como supervisor (rol exacto requerido)
curl -s -X POST "http://localhost:8000/api/v1/workflows/executions/$EXEC_ID/advance/" \
  -H "Authorization: Bearer $TOKEN_SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"action":"approved","comment":"Revision OK, todo en orden"}' \
  | python3 -m json.tool
# Esperado: 200, status sigue "in_progress", current_step avanza al paso 2
```

### Intentar avanzar con un rol insuficiente (esperado: 403)

```bash
# Editor no tiene rol suficiente para el paso 2 (requiere org_admin)
curl -s -X POST "http://localhost:8000/api/v1/workflows/executions/$EXEC_ID/advance/" \
  -H "Authorization: Bearer $TOKEN_EDITOR" \
  -H "Content-Type: application/json" \
  -d '{"action":"approved","comment":"Intento de editor"}' | python3 -m json.tool
# Esperado: 403 PERMISSION_DENIED
```

### Avanzar el paso final — Admin aprueba

```bash
curl -s -X POST "http://localhost:8000/api/v1/workflows/executions/$EXEC_ID/advance/" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"action":"approved","comment":"Aprobado para publicacion"}' \
  | python3 -m json.tool
# Esperado: 200, execution.status = "completed"

# Verificar que el documento ahora está "approved"
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; print('status:', json.load(sys.stdin)['data']['status'])"
# Esperado: "approved"
```

### Ver logs de la ejecución

```bash
curl -s "http://localhost:8000/api/v1/workflows/executions/$EXEC_ID/logs/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: 2 entradas (una por cada advance), con action, comment y performed_by_email
```

### Flujo de rechazo (en documento nuevo)

```bash
# Crear nuevo documento para prueba de rechazo
DOC_REJECT_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/contrato.pdf" \
  -F "name=contrato_rechazable.pdf" \
  -F "folder_id=$SUBFOLDER_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

EXEC_REJECT_ID=$(curl -s -X POST http://localhost:8000/api/v1/workflows/executions/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\":\"$DOC_REJECT_ID\",\"template_id\":\"$TEMPLATE_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Rechazar en el paso 1
curl -s -X POST "http://localhost:8000/api/v1/workflows/executions/$EXEC_REJECT_ID/advance/" \
  -H "Authorization: Bearer $TOKEN_SUPERVISOR" \
  -H "Content-Type: application/json" \
  -d '{"action":"rejected","comment":"Falta firma del notario"}' | python3 -m json.tool

# Verificar que el documento pasó a "rejected"
curl -s "http://localhost:8000/api/v1/documents/$DOC_REJECT_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; print('status:', json.load(sys.stdin)['data']['status'])"
# Esperado: "rejected"
```

---

## Nivel 8: Auditoría

Todas las acciones importantes generan un `AuditLog` inmutable. El endpoint de audit logs es de solo lectura y requiere rol `auditor`, `org_admin` o `super_admin`.

### Listar audit logs

```bash
# Como auditor de Org A
curl -s http://localhost:8000/api/v1/audit-logs/ \
  -H "Authorization: Bearer $TOKEN_AUDITOR" | python3 -m json.tool
```

Respuesta esperada: lista paginada de logs con campos `action`, `entity_type`, `entity_id`, `user_id`, `created_at`, `old_values`, `new_values`.

### Verificar que el viewer no puede ver audit logs (403)

```bash
curl -s http://localhost:8000/api/v1/audit-logs/ \
  -H "Authorization: Bearer $TOKEN_VIEWER" | python3 -m json.tool
# Esperado: 403 PERMISSION_DENIED
```

### Filtrar por tipo de acción

```bash
# Solo eventos de login
curl -s "http://localhost:8000/api/v1/audit-logs/?action=login" \
  -H "Authorization: Bearer $TOKEN_AUDITOR" | python3 -m json.tool

# Solo creaciones de documentos
curl -s "http://localhost:8000/api/v1/audit-logs/?action=create&entity_type=document" \
  -H "Authorization: Bearer $TOKEN_AUDITOR" | python3 -m json.tool

# Rango de fechas
curl -s "http://localhost:8000/api/v1/audit-logs/?created_after=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN_AUDITOR" | python3 -m json.tool
```

Parámetros de filtro disponibles: `action`, `entity_type`, `entity_id`, `user` (UUID), `created_after` (datetime ISO 8601), `created_before` (datetime ISO 8601).

### Verificar que leer audit logs NO genera audit log

```bash
# Contar logs antes
COUNT_BEFORE=$(python manage.py shell -c "from apps.audit.models import AuditLog; print(AuditLog.objects.count())")

# Leer audit logs varias veces
curl -s http://localhost:8000/api/v1/audit-logs/ -H "Authorization: Bearer $TOKEN_AUDITOR" > /dev/null
curl -s http://localhost:8000/api/v1/audit-logs/ -H "Authorization: Bearer $TOKEN_AUDITOR" > /dev/null

# Contar logs después — debe ser el mismo número
COUNT_AFTER=$(python manage.py shell -c "from apps.audit.models import AuditLog; print(AuditLog.objects.count())")

echo "Antes: $COUNT_BEFORE | Después: $COUNT_AFTER"
# Esperado: mismo número — leer logs no genera logs nuevos
```

### Verificar inmutabilidad del AuditLog

```bash
python manage.py shell -c "
from apps.audit.models import AuditLog

log = AuditLog.objects.first()
log.action = 'create'  # intento de modificacion

try:
    log.save()
    print('ERROR: el save no deberia haber funcionado')
except RuntimeError as e:
    print('OK - AuditLog es inmutable:', e)

try:
    log.delete()
    print('ERROR: el delete no deberia haber funcionado')
except RuntimeError as e:
    print('OK - AuditLog no se puede borrar:', e)
"
```

---

## Nivel 9: Cleanup de blobs huérfanos

Cuando un documento se soft-deletes, su blob en MinIO queda. La tarea `cleanup_orphan_blobs` lo elimina periódicamente (03:00 UTC diario). Aquí se prueba manualmente.

### Preparar: crear y borrar un documento

```bash
# Subir documento
DOC_ORPHAN_ID=$(curl -s -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/contrato.pdf" \
  -F "name=orphan_test.pdf" \
  -F "folder_id=$SUBFOLDER_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Obtener la ruta del blob antes de borrar
STORAGE_PATH=$(curl -s "http://localhost:8000/api/v1/documents/$DOC_ORPHAN_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['storage_path'])")
echo "Storage path: $STORAGE_PATH"

# Soft-delete del documento
curl -s -X DELETE "http://localhost:8000/api/v1/documents/$DOC_ORPHAN_ID/" \
  -H "Authorization: Bearer $TOKEN_A"
# Esperado: 204

# Verificar que el blob todavía existe en MinIO (antes del cleanup)
mc ls "local/saasvault-documents/$STORAGE_PATH" 2>/dev/null && echo "Blob existe en MinIO" || echo "Blob no encontrado"
```

### Ajustar grace period a 0 para prueba inmediata

La tarea respeta un período de gracia para evitar borrar uploads en vuelo. Para pruebas manuales, ponerlo en 0 horas en `.env`:

```
ORPHAN_BLOB_GRACE_HOURS=0
```

Reiniciar Django y el worker después de cambiar `.env`.

### Ejecutar cleanup manualmente

```bash
# Opción 1: desde el shell de Django (más rápido)
python manage.py shell -c "
from apps.documents.services import cleanup_service
result = cleanup_service.delete_orphan_blobs(grace_hours=0)
print('Resultado:', result)
# Esperado: {'scanned': N, 'deleted': M, 'skipped_grace': 0}
"
```

```bash
# Opción 2: dispatch de la tarea Celery (requiere worker corriendo)
python manage.py shell -c "
from apps.documents.tasks.document_tasks import cleanup_orphan_blobs
result = cleanup_orphan_blobs.delay()
print('Task ID:', result.id)
print('Resultado:', result.get(timeout=30))
"
```

### Verificar que el blob desapareció de MinIO

```bash
mc ls "local/saasvault-documents/$STORAGE_PATH" 2>/dev/null && echo "Blob AUN existe" || echo "Blob eliminado correctamente"
```

### Restaurar grace period

Volver a poner `ORPHAN_BLOB_GRACE_HOURS=24` en `.env` después de la prueba.

---

## Nivel 10: Análisis IA (opcional)

Este nivel solo aplica si `ANTHROPIC_API_KEY` está configurada en `.env`. Sin la key, el endpoint devuelve 503.

### Verificar si la feature está activa

```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/analyze/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
```

- Si `ANTHROPIC_API_KEY` está vacía: `503 {"error": {"code": "AI_SERVICE_UNAVAILABLE", ...}}`
- Si está configurada: `202 {"data": {"message": "AI analysis queued."}, "meta": {}}`

### Configurar la key y probar

En `.env`:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Reiniciar Django y el worker. Luego:

```bash
# Disparar análisis (asíncrono — el worker ejecuta la tarea)
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/analyze/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
# Esperado: 202 Accepted

# Esperar a que el worker procese (segundos a minutos según la API de Anthropic)
# Verificar resultado en metadata["ai_analysis"]
sleep 10
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/" \
  -H "Authorization: Bearer $TOKEN_A" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
ai = d.get('metadata', {}).get('ai_analysis', 'pendiente o no disponible')
print('AI analysis:', json.dumps(ai, indent=2) if isinstance(ai, dict) else ai)
"
```

### Verificar que viewer no puede disparar análisis

```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/analyze/" \
  -H "Authorization: Bearer $TOKEN_VIEWER" | python3 -m json.tool
# Esperado: 403 PERMISSION_DENIED (requiere Editor o superior)
```

---

## Apéndice: Comandos útiles

### psql — Consultas directas a PostgreSQL

```bash
# Conectar
PGPASSWORD=saasvault_pass_local psql -h localhost -U saasvault_user -d saasvault_db

# Ver últimos 10 audit logs
SELECT action, entity_type, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 10;

# Ver documentos con ocr_status
SELECT name, status, ocr_status, LENGTH(ocr_content) AS ocr_chars FROM documents WHERE deleted_at IS NULL;

# Ver organizaciones activas
SELECT id, name, slug, is_active FROM organizations;

# Ver usuarios por org
SELECT u.email, u.role, o.name AS org FROM users u JOIN organizations o ON u.organization_id = o.id;

# Verificar un documento soft-deleted (all_objects no existe en SQL; deleted_at filtra)
SELECT id, name, deleted_at FROM documents WHERE deleted_at IS NOT NULL;

# Ver execuciones de workflow activas
SELECT we.id, we.status, d.name AS doc, we.started_at
FROM workflow_executions we
JOIN documents d ON we.document_id = d.id
WHERE we.status IN ('pending','in_progress');
```

### redis-cli — Inspección de Redis

> Requiere `redis-tools` (`sudo apt-get install -y redis-tools`).


```bash
# Ping
redis-cli ping

# Ver todas las keys (no hacer en prod)
redis-cli keys '*'

# Ver keys de Celery
redis-cli -n 1 keys '*'  # broker
redis-cli -n 2 keys '*'  # results

# Monitor de comandos en tiempo real
redis-cli monitor
```

### MinIO mc — Operaciones de storage

```bash
# Configurar alias (una sola vez)
mc alias set local http://localhost:9000 minioadmin minioadmin

# Listar objetos del bucket
mc ls local/saasvault-documents/

# Ver tamaño total del bucket
mc du local/saasvault-documents/

# Descargar un objeto específico
mc cp "local/saasvault-documents/<ruta>" /tmp/descarga_manual

# Eliminar objeto manualmente (simular cleanup)
mc rm "local/saasvault-documents/<ruta>"
```

### Celery — Inspección de workers y tareas

```bash
# Ver workers activos
celery -A config.celery inspect active

# Ver tareas registradas
celery -A config.celery inspect registered

# Ejecutar tarea manualmente desde Python
python manage.py shell -c "
from apps.documents.tasks.document_tasks import process_ocr
# Reemplazar con un DOC_ID real cuyo ocr_status sea pending o failed
result = process_ocr.delay('<doc-uuid>')
print('Task ID:', result.id)
# result.get(timeout=30) bloquea hasta el resultado
"

# Ejecutar cleanup manualmente (ver Nivel 9)
python manage.py shell -c "
from apps.documents.tasks.document_tasks import cleanup_orphan_blobs
r = cleanup_orphan_blobs.delay()
print(r.get(timeout=60))
"
```

### Tabla de referencia rápida de casos de prueba

| Caso | Endpoint | Rol requerido | Resultado esperado |
|---|---|---|---|
| Health sin token | GET `/health/` | Ninguno | 200 `{status: ok}` |
| Login correcto | POST `/auth/login/` | — | 200 + tokens |
| Login credenciales incorrectas | POST `/auth/login/` | — | 401 |
| Refresh tras logout | POST `/auth/refresh/` | — | 401 token_blacklisted |
| Crear carpeta (Editor) | POST `/folders/` | editor+ | 201 |
| Crear carpeta (Viewer) | POST `/folders/` | viewer | 403 |
| Borrar carpeta con hijos | DELETE `/folders/{id}/` | org_admin+ | 409 CONFLICT |
| Upload PDF válido | POST `/documents/` | editor+ | 201, ocr_status: pending |
| Upload EXE disfrazado | POST `/documents/` | editor+ | 400 INVALID_MIME_TYPE |
| Upload archivo >50MB | POST `/documents/` | editor+ | 400 FILE_TOO_LARGE |
| Presigned URL | GET `/documents/{id}/download/` | member | 200 + URL |
| Reprocess OCR | POST `/documents/{id}/reprocess-ocr/` | editor+ | 202 Accepted |
| Análisis IA sin key | POST `/documents/{id}/analyze/` | editor+ | 503 AI_SERVICE_UNAVAILABLE |
| Buscar texto | GET `/search/?q=texto` | member | 200 lista filtrada |
| Ver otra org (aislamiento) | GET `/folders/{id_org_A}/` | admin_org_B | 404 NOT_FOUND |
| Audit logs (Auditor) | GET `/audit-logs/` | auditor | 200 lista |
| Audit logs (Viewer) | GET `/audit-logs/` | viewer | 403 |
| Iniciar workflow | POST `/workflows/executions/` | editor+ | 201 + doc → under_review |
| Iniciar 2° ejecución activa | POST `/workflows/executions/` | editor+ | 409 WORKFLOW_ALREADY_ACTIVE |
| Avanzar paso (rol incorrecto) | POST `/executions/{id}/advance/` | insuficiente | 403 |
| Aprobar paso final | POST `/executions/{id}/advance/` | rol requerido | 200 + doc → approved |
| Rechazar en cualquier paso | POST `/executions/{id}/advance/` | rol requerido | 200 + doc → rejected |

### Tabla de variables de entorno relevantes para pruebas

| Variable | Default en dev | Para qué sirve en testing |
|---|---|---|
| `ORPHAN_BLOB_GRACE_HOURS` | `24` | Poner en `0` para probar cleanup inmediato |
| `ANTHROPIC_API_KEY` | vacía | Rellenar para activar análisis IA |
| `OCR_LANGUAGES` | `spa+eng` | Idiomas de Tesseract |
| `OCR_PDF_DPI` | `200` | Resolución para rasterizar PDFs |
| `SENTRY_DSN` | vacía | Rellenar para enviar errores a Sentry |
| `CELERY_TASK_MAX_RETRIES` | `3` | Reintentos máximos de tareas fallidas |
