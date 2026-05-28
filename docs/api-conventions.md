# docs/api-conventions.md — Convenciones REST SasVault

> Referencia definitiva para el diseño de la API.
> Todo endpoint nuevo debe seguir estas convenciones sin excepción.

---

## 1. Versionado

Toda URL pública de la API lleva el prefijo `/api/v1/`.

```
https://saasvault.example.com/api/v1/documents/
```

Cuando haya cambios breaking, se creará `/api/v2/` manteniendo v1 activa por un período de deprecación.

---

## 2. Recursos y URLs

### Naming

- URLs en **kebab-case** y **plural**: `/audit-logs/`, `/workflow-steps/`
- No usar verbos en URLs: ❌ `/get-document/`, ✅ `/documents/{id}/`
- Acciones no CRUD se expresan como sub-recursos: `/documents/{id}/download/`

### Jerarquía de recursos

```
/organizations/
/organizations/{id}/

/users/
/users/{id}/

/folders/
/folders/{id}/
/folders/{id}/children/
/folders/{id}/documents/

/documents/
/documents/{id}/
/documents/{id}/versions/
/documents/{id}/download/
/documents/{id}/analyze/

/workflows/
/workflows/{id}/
/workflows/{id}/steps/
/workflows/{id}/execute/

/workflow-executions/
/workflow-executions/{id}/
/workflow-executions/{id}/advance/

/audit-logs/
/audit-logs/{id}/

/search/

/auth/login/
/auth/refresh/
/auth/logout/
/auth/me/
```

---

## 3. Métodos HTTP

| Método | Uso | Idempotente |
|--------|-----|-------------|
| GET | Lectura, nunca modifica estado | Sí |
| POST | Creación de recursos, acciones | No |
| PATCH | Actualización parcial (campos específicos) | No |
| PUT | Reemplazo completo del recurso | Sí |
| DELETE | Eliminación (soft en entidades críticas) | Sí |

**Preferir PATCH sobre PUT** en la mayoría de casos.

---

## 4. Formato de respuesta — Envelope obligatorio

### Respuesta exitosa — objeto único

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Contrato_2024.pdf",
    "status": "draft",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Respuesta exitosa — lista paginada

```json
{
  "data": [
    { "id": "...", "name": "doc1.pdf" },
    { "id": "...", "name": "doc2.pdf" }
  ],
  "meta": {
    "count": 45,
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "next": "http://localhost:8000/api/v1/documents/?page=2",
    "previous": null
  }
}
```

### Respuesta de error

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with id X does not exist or you don't have access.",
    "details": {}
  }
}
```

### Error de validación (400)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request data is invalid.",
    "details": {
      "name": ["This field is required."],
      "file": ["File size exceeds the 50MB limit."]
    }
  }
}
```

---

## 5. Códigos HTTP

| Situación | Código | Cuándo |
|-----------|--------|--------|
| GET exitoso | 200 | Recurso encontrado |
| POST exitoso | 201 | Recurso creado |
| PATCH/PUT exitoso | 200 | Recurso actualizado |
| DELETE exitoso | 204 | Recurso eliminado (sin body) |
| Validación fallida | 400 | Datos de entrada inválidos |
| Token inválido/expirado | 401 | No autenticado |
| Sin permiso | 403 | Autenticado pero sin acceso |
| No encontrado | 404 | Recurso no existe en esta org |
| Método no permitido | 405 | HTTP method no soportado |
| Rate limit excedido | 429 | Demasiadas requests |
| Error interno | 500 | Error no manejado del servidor |

---

## 6. Paginación

Usar paginación basada en páginas (no cursor) para v1.

### Parámetros de query

```
GET /api/v1/documents/?page=2&page_size=20
```

Defaults:
- `page`: 1
- `page_size`: 20
- `page_size` máximo: 100

Configurar en DRF settings:
```python
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
}
```

---

## 7. Filtros

Usar `django-filter` para filtros declarativos.

```
GET /api/v1/documents/?status=draft&folder=uuid&created_after=2024-01-01
GET /api/v1/audit-logs/?action=create&entity_type=document&user=uuid
GET /api/v1/documents/?ordering=-created_at
GET /api/v1/documents/?q=contrato+arrendamiento
```

### Parámetros estándar de filtrado

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `q` | string | Búsqueda full-text |
| `ordering` | string | Campo de orden, prefijo `-` para desc |
| `page` | int | Número de página |
| `page_size` | int | Resultados por página |
| `created_after` | ISO 8601 | Filtro por fecha inicio |
| `created_before` | ISO 8601 | Filtro por fecha fin |

---

## 8. Autenticación en headers

```
Authorization: Bearer <access_token>
```

Todos los endpoints excepto `/auth/login/` requieren este header.

### Flujo de tokens

```
POST /api/v1/auth/login/
Body: { "email": "...", "password": "..." }
Response: { "data": { "access": "...", "refresh": "..." } }

→ Usar access en Authorization header
→ Cuando access expira (401), usar refresh:

POST /api/v1/auth/refresh/
Body: { "refresh": "..." }
Response: { "data": { "access": "...", "refresh": "..." } }  ← nuevo refresh (rotating)

→ Logout:
POST /api/v1/auth/logout/
Body: { "refresh": "..." }
Response: 204  ← refresh en blacklist
```

---

## 9. Upload de archivos

Usar `multipart/form-data` para uploads.

```
POST /api/v1/documents/
Content-Type: multipart/form-data

file: <binary>
name: "Contrato 2024"
description: "Contrato de arrendamiento local comercial"
folder_id: "uuid-opcional"
tags: ["contrato", "legal", "2024"]
```

Respuesta `201`:
```json
{
  "data": {
    "id": "uuid",
    "name": "Contrato 2024",
    "status": "draft",
    "mime_type": "application/pdf",
    "file_size": 204800,
    "version": 1,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

## 10. Descarga de archivos

No devolver archivos binarios directamente desde Django. Usar **presigned URLs** de MinIO/S3.

```
GET /api/v1/documents/{id}/download/

Response 200:
{
  "data": {
    "url": "https://minio.../file.pdf?X-Amz-Signature=...",
    "expires_in": 3600
  }
}
```

El cliente usa esa URL para descargar directamente del storage.

---

## 11. Timestamps

Todos los timestamps en formato **ISO 8601 UTC**:

```
"created_at": "2024-01-15T10:30:00Z"
"updated_at": "2024-01-15T14:22:30Z"
```

---

## 12. IDs

Todos los IDs son **UUID v4** en formato string:

```
"id": "550e8400-e29b-41d4-a716-446655440000"
```

Nunca exponer IDs numéricos secuenciales (evita enumeración de recursos).

---

## 13. Documentación automática de la API

Usar `drf-spectacular` para generar OpenAPI 3.0 automáticamente.

```
GET /api/schema/          → descarga el schema YAML/JSON
GET /api/docs/            → Swagger UI interactivo
GET /api/redoc/           → ReDoc UI
```

Configurar en urls.py:
```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

La documentación generada automáticamente es parte del portafolio — los recruiters técnicos la valoran.
