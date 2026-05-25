# docs/database-conventions.md — Convenciones de Base de Datos DocuVault

> Referencia de diseño de base de datos para el proyecto.
> Seguir estas convenciones garantiza consistencia y performance.

---

## 1. Motor de base de datos

**PostgreSQL 16** — única opción. No SQLite (ni en tests si se puede evitar), no MySQL.

En tests usar `pytest-django` con `@pytest.mark.django_db` — pytest-django puede usar la misma PostgreSQL de desarrollo o una DB de test separada (configurada en settings/test.py).

---

## 2. Modelo base — BaseModel

Todo modelo hereda de `BaseModel`. Ver `apps/core/models/base.py`.

Campos automáticos en todo modelo:
- `id`: UUID v4, primary key, no editable
- `created_at`: datetime auto al crear
- `updated_at`: datetime auto al modificar
- `deleted_at`: datetime null para soft delete

---

## 3. Naming conventions

### Tablas
- snake_case, plural
- Prefijo de app cuando hay ambigüedad

```
organizations_organization
auth_user
documents_document
documents_document_version
documents_folder
workflows_workflow_template
workflows_workflow_step
workflows_workflow_execution
audit_audit_log
```

Django genera el nombre automáticamente como `{app_label}_{model_name}`. Especificar explícitamente en Meta cuando sea necesario:
```python
class Meta:
    db_table = 'documents_document'
```

### Campos
- snake_case, singular
- FK: `{modelo_referenciado}` o nombre descriptivo si hay múltiples FK al mismo modelo
- Campos booleanos: `is_active`, `is_verified`, no `active`, `verified`
- Campos opcionales: siempre `null=True, blank=True` juntos

### Índices
```
idx_{tabla}_{campo}
idx_{tabla}_{campo1}_{campo2}
idx_{tabla}_{campo}_gin       ← para índices GIN
```

---

## 4. Esquema de tablas principales

### organizations_organization
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
name            VARCHAR(255) NOT NULL
slug            VARCHAR(255) NOT NULL UNIQUE
is_active       BOOLEAN NOT NULL DEFAULT TRUE
settings        JSONB NOT NULL DEFAULT '{}'
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at      TIMESTAMPTZ

INDEX: idx_organization_slug ON (slug)
INDEX: idx_organization_active ON (is_active) WHERE is_active = TRUE
```

### auth_user (Custom User)
```sql
id              UUID PRIMARY KEY
email           VARCHAR(254) NOT NULL UNIQUE
password        VARCHAR(128) NOT NULL
organization_id UUID NOT NULL REFERENCES organizations_organization(id)
role            VARCHAR(20) NOT NULL  -- super_admin, org_admin, etc.
is_active       BOOLEAN NOT NULL DEFAULT TRUE
last_login_at   TIMESTAMPTZ
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
deleted_at      TIMESTAMPTZ

INDEX: idx_user_organization ON (organization_id)
INDEX: idx_user_email ON (email)
INDEX: idx_user_org_role ON (organization_id, role)
```

### documents_folder
```sql
id              UUID PRIMARY KEY
organization_id UUID NOT NULL REFERENCES organizations_organization(id)
parent_id       UUID REFERENCES documents_folder(id)  -- null = carpeta raíz
name            VARCHAR(255) NOT NULL
owner_id        UUID NOT NULL REFERENCES auth_user(id)
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
deleted_at      TIMESTAMPTZ

INDEX: idx_folder_org_parent ON (organization_id, parent_id)
UNIQUE: uq_folder_name_parent ON (organization_id, parent_id, name)
        WHERE deleted_at IS NULL
```

### documents_document
```sql
id              UUID PRIMARY KEY
organization_id UUID NOT NULL REFERENCES organizations_organization(id)
folder_id       UUID REFERENCES documents_folder(id)
created_by_id   UUID NOT NULL REFERENCES auth_user(id)
name            VARCHAR(255) NOT NULL
description     TEXT NOT NULL DEFAULT ''
mime_type       VARCHAR(127) NOT NULL
file_size       BIGINT NOT NULL  -- bytes
checksum        VARCHAR(64) NOT NULL  -- SHA256 hex
storage_path    VARCHAR(1024) NOT NULL
status          VARCHAR(20) NOT NULL DEFAULT 'draft'
version         INTEGER NOT NULL DEFAULT 1
tags            JSONB NOT NULL DEFAULT '[]'
metadata        JSONB NOT NULL DEFAULT '{}'
ocr_content     TEXT  -- resultado del OCR
search_vector   TSVECTOR  -- actualizado por signal/trigger
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
deleted_at      TIMESTAMPTZ

INDEX: idx_documents_org_status ON (organization_id, status)
INDEX: idx_documents_org_folder ON (organization_id, folder_id)
INDEX: idx_documents_org_created ON (organization_id, created_at DESC)
INDEX: idx_documents_search_vector_gin ON (search_vector) USING GIN
INDEX: idx_documents_tags_gin ON (tags) USING GIN
```

### documents_document_version
```sql
id              UUID PRIMARY KEY
document_id     UUID NOT NULL REFERENCES documents_document(id)
version_number  INTEGER NOT NULL
storage_path    VARCHAR(1024) NOT NULL
file_size       BIGINT NOT NULL
checksum        VARCHAR(64) NOT NULL
created_by_id   UUID NOT NULL REFERENCES auth_user(id)
change_description TEXT NOT NULL DEFAULT ''
created_at      TIMESTAMPTZ NOT NULL

UNIQUE: uq_document_version ON (document_id, version_number)
INDEX: idx_doc_version_document ON (document_id)
```

### audit_audit_log
```sql
id              BIGSERIAL PRIMARY KEY  -- no UUID: performance en tabla de alta escritura
organization_id UUID NOT NULL REFERENCES organizations_organization(id)
user_id         UUID REFERENCES auth_user(id)  -- null si es acción del sistema
entity_type     VARCHAR(50) NOT NULL  -- 'document', 'folder', 'user', etc.
entity_id       VARCHAR(36) NOT NULL  -- UUID del recurso afectado
action          VARCHAR(30) NOT NULL  -- 'create', 'update', 'delete', 'view', 'login'
old_values      JSONB
new_values      JSONB
ip_address      INET
user_agent      TEXT
metadata        JSONB NOT NULL DEFAULT '{}'
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Sin updated_at ni deleted_at: los logs son inmutables
INDEX: idx_audit_org_created ON (organization_id, created_at DESC)
INDEX: idx_audit_org_entity ON (organization_id, entity_type, entity_id)
INDEX: idx_audit_user ON (user_id)
```

---

## 5. Uso de JSONB

Usar JSONB (no JSON) para:
- `settings` en Organization: configuración flexible de la org
- `metadata` en Document: campos variables por tipo de documento
- `tags` en Document: array de strings con índice GIN para búsqueda
- `old_values` / `new_values` en AuditLog: estado anterior y posterior
- `config` en WorkflowTemplate: configuración del flujo

```python
# Ejemplo de acceso a JSONB en queries Django
Document.objects.filter(
    organization=org,
    metadata__contract_type='rental'  # acceso a key dentro del JSONB
)

Document.objects.filter(
    tags__contains=['contrato']  # buscar en array JSONB
)
```

---

## 6. Full Text Search

### Configuración del campo

```python
from django.contrib.postgres.search import SearchVectorField

class Document(BaseModel):
    search_vector = SearchVectorField(null=True, blank=True)
```

### Actualización del vector con signal

```python
from django.db.models.signals import post_save
from django.contrib.postgres.search import SearchVector

@receiver(post_save, sender=Document)
def update_search_vector(sender, instance, **kwargs):
    Document.objects.filter(pk=instance.pk).update(
        search_vector=(
            SearchVector('name', weight='A', config='spanish') +
            SearchVector('description', weight='B', config='spanish') +
            SearchVector('ocr_content', weight='C', config='spanish')
        )
    )
```

### Búsqueda con ranking

```python
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchHeadline

def search_documents(organization, query_text):
    query = SearchQuery(query_text, config='spanish')
    return (
        Document.objects
        .filter(organization=organization, search_vector=query)
        .annotate(
            rank=SearchRank('search_vector', query),
            headline=SearchHeadline(
                'name', query,
                config='spanish',
                start_sel='<mark>',
                stop_sel='</mark>',
            )
        )
        .order_by('-rank')
    )
```

---

## 7. Transacciones

Usar `transaction.atomic()` en services que hacen múltiples escrituras relacionadas.

```python
from django.db import transaction

@transaction.atomic
def create_document(organization, user, file, name):
    # Si cualquier operación falla, todo el bloque hace rollback
    document = Document.objects.create(...)
    DocumentVersion.objects.create(document=document, ...)
    # Si esto lanza excepción, el document tampoco queda guardado
    audit_service.log(...)
    return document
```

---

## 8. Optimización de queries

### select_related y prefetch_related

```python
# Siempre en selectors, nunca dejar N+1 queries
Document.objects.filter(organization=org).select_related(
    'created_by',
    'folder',
    'organization',
)

WorkflowExecution.objects.filter(organization=org).prefetch_related(
    'steps',
    'steps__performed_by',
)
```

### EXPLAIN ANALYZE

Verificar índices con EXPLAIN ANALYZE en queries críticas:

```python
# En Django shell o en tests de performance
from django.db import connection

qs = Document.objects.filter(organization=org, status='draft')
print(qs.explain(verbose=True, analyze=True))
```

---

## 9. Migraciones

### Convenciones

```bash
# Crear migración con nombre descriptivo
python manage.py makemigrations documents --name="add_search_vector_to_document"

# Aplicar
python manage.py migrate

# Ver SQL que genera la migración (antes de aplicar)
python manage.py sqlmigrate documents 0003_add_search_vector_to_document
```

### Reglas

- Nunca modificar migraciones ya aplicadas y commiteadas
- Cada migración va en su propio commit
- Incluir migraciones de datos (data migrations) cuando sea necesario en vez de scripts externos
- En producción: siempre revisar el SQL de la migración antes de aplicar en tablas grandes

---

## 10. Consideraciones de performance

### Tabla audit_log

La tabla `audit_log` crecerá muy rápido. Consideraciones:
- Usar `BigAutoField` como PK (no UUID) para inserción más rápida
- Índice en `(organization_id, created_at DESC)` para queries típicas
- Considerar particionamiento por fecha en el futuro (no necesario en v1)
- Tarea Celery mensual para archivar logs antiguos (> 1 año)

### Tabla documents

- Paginación obligatoria en todos los listados
- Nunca `Document.objects.all()` sin filtro de organización
- `select_related` siempre para evitar N+1
