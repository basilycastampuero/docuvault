# Guía de despliegue a producción — SasVault

> Esta guía asume que conoces Django y React bien, pero nunca has desplegado
> nada profesionalmente. Cada decisión viene con su porqué. Léela de principio
> a fin antes de ejecutar cualquier comando.

---

## Índice

1. [Por qué `runserver` no es producción](#1-por-qué-runserver-no-es-producción)
2. [La arquitectura de producción — el viaje de un request](#2-la-arquitectura-de-producción--el-viaje-de-un-request)
3. [Multi-stage Dockerfiles — por qué dos stages](#3-multi-stage-dockerfiles--por-qué-dos-stages)
4. [docker-compose.prod.yml — los 8 servicios](#4-docker-composeprodymll--los-8-servicios)
5. [Nginx — el guardián de la puerta](#5-nginx--el-guardián-de-la-puerta)
6. [Variables de entorno en producción — qué cambia y por qué](#6-variables-de-entorno-en-producción--qué-cambia-y-por-qué)
7. [El certificado SSL — autofirmado vs real](#7-el-certificado-ssl--autofirmado-vs-real)
8. [Scripts de deploy y backup](#8-scripts-de-deploy-y-backup)
9. [Cómo diagnosticar fallos comunes](#9-cómo-diagnosticar-fallos-comunes)
10. [Glosario](#10-glosario)

---

## 1. Por qué `runserver` no es producción

Cuando ejecutas `python manage.py runserver` en tu máquina, Django levanta un
servidor web minimalista pensado exclusivamente para que el desarrollador vea
resultados rápido. No está diseñado para recibir tráfico real. Veamos por qué.

### Qué hace `runserver` internamente

`runserver` es **monohilo y monoproceso**: atiende exactamente una petición a
la vez. Si un request tarda 2 segundos (por ejemplo, una consulta lenta a la
base de datos), todos los demás usuarios que lleguen en ese intervalo esperan
en cola. Con 10 usuarios simultáneos, el décimo espera 20 segundos. Eso no es
aceptable en ningún entorno real.

Además:

- **No maneja SSL.** Sirve HTTP plano. Los datos viajan sin cifrar por la red.
- **Expone información de debug.** Con `DEBUG=True`, cualquier excepción no
  capturada muestra el traceback completo, las variables locales de cada frame,
  y la configuración de Django en el navegador del usuario. Un atacante que
  provoque un error a propósito obtiene un mapa detallado de tu aplicación.
- **No sirve archivos estáticos en modo eficiente.** En producción, Django
  delega los estáticos a un servidor dedicado (Nginx). `runserver` los sirve
  directamente desde Python, que es mucho más lento y no tiene capacidades de
  caché HTTP.
- **No tolera caídas.** Si el proceso muere (por un bug, por memoria agotada),
  nadie lo reinicia. Los usuarios ven la página muerta hasta que tú lo notes.

### La analogía

`runserver` es como abrir tu laptop en la calle y decirle a la gente que se
acerque si quiere consultar el catálogo de tu tienda. Funciona para que vea
un amigo. No funciona cuando llegan 500 clientes.

Gunicorn, en cambio, es el cajero automático de un banco con vidrio blindado:
robusto, con múltiples ventanillas (workers), detrás de una capa de seguridad
(Nginx/SSL), y con un proceso supervisor que lo reinicia si se cae.

### Qué es Gunicorn

**Gunicorn** (Green Unicorn) es un servidor WSGI para Python. WSGI (Web Server
Gateway Interface) es el estándar que define cómo un servidor web habla con una
aplicación Python — es el "enchufe" que conecta Nginx con Django.

Gunicorn usa el modelo **pre-fork**: al arrancar, crea N procesos hijo (workers)
de antemano, cada uno con una copia completa de tu aplicación Django cargada en
memoria. Cuando llega un request, Gunicorn se lo asigna al primer worker libre.
Si todos están ocupados, el request espera. Si un worker muere, Gunicorn crea
uno nuevo automáticamente.

En `docker-compose.prod.yml`, el servicio `web` arranca Gunicorn así:

```
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

- `config.wsgi:application` — el objeto WSGI de Django (archivo
  `backend/config/wsgi.py`).
- `--bind 0.0.0.0:8000` — escucha en el puerto 8000 de todas las interfaces
  del contenedor (no lo exponemos al mundo; Nginx lo intercepta primero).
- `--workers 2` — dos procesos paralelos. Para un VPS de 2 cores, la fórmula
  clásica es `2 * num_cores + 1`. Con 2 workers, podemos atender 2 requests
  simultáneos sin que uno bloquee al otro.
- `--timeout 120` — si un worker tarda más de 120 segundos en responder, se
  lo mata y se crea uno nuevo. Evita workers colgados por consultas DB
  interminables.

---

## 2. La arquitectura de producción — el viaje de un request

Antes de tocar un archivo, necesitas tener claro qué pasa cuando un usuario
abre el navegador y escribe la URL de SasVault.

```
                         Internet
                             |
                    ┌────────▼────────┐
                    │   Nginx :443    │  ← termina SSL, distribuye tráfico
                    │   (puerto 443)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────────┐
              │              │                  │
     /api/*   │    /admin/*  │    / (todo lo    │
     /docs/*  │    /static/* │     demás)       │
              │              │                  │
    ┌─────────▼──────────────▼┐   ┌─────────────▼────────┐
    │   Gunicorn :8000        │   │ /usr/share/nginx/html │
    │   (Django + DRF)        │   │ (archivos del build   │
    │                         │   │  de React/Vite)       │
    └─────────────────────────┘   └──────────────────────┘
              │
    ┌─────────┼──────────────────────┐
    │         │                      │
    ▼         ▼                      ▼
PostgreSQL  Redis             MinIO :9000
(datos)  (caché/broker)    (archivos subidos)
```

Cada flecha es una decisión de diseño con su razón. Sigámoslas.

### Por qué Nginx está adelante

**1. Terminación SSL.** Nginx descifra el tráfico HTTPS una sola vez y reenvía
HTTP plano a Gunicorn dentro de la red privada de Docker. Gunicorn no necesita
saber nada de TLS; se lo delega a quien es experto en eso. Este patrón se llama
"SSL termination" y es universal en arquitecturas web.

**2. Servir archivos estáticos sin tocar Python.** Cuando el navegador pide
`/static/admin/css/base.css` (el CSS del panel de admin de Django), Nginx lo
sirve directamente desde el sistema de archivos, sin pasar por Gunicorn. Nginx
está optimizado para esto: usa `sendfile()` del kernel, caché de disco, y puede
servir miles de archivos estáticos por segundo. Si esa petición llegara a
Gunicorn, ocuparía un worker durante el tiempo que tarde en leer el archivo y
enviarlo, bloqueando una petición de API real.

**3. El frontend compilado vive dentro de Nginx.** El `Dockerfile` del frontend
compila React con Vite (`npm run build`) y deja los archivos resultantes en
`/app/dist`. Ese directorio se copia dentro de la imagen de Nginx, en
`/usr/share/nginx/html`. Cuando el usuario pide `/`, `/login`, `/documents/123`,
Nginx sirve el `index.html` y los chunks JS directamente. Sin Python, sin
Django. Eficiencia máxima.

**4. Protección básica contra abuso.** Nginx puede limitar el rate de requests
por IP, rechazar métodos HTTP no permitidos, y bloquear patrones de URLs
maliciosas antes de que el request llegue siquiera a Django. Es la primera línea
de defensa.

**5. Un solo punto de entrada.** En vez de exponer los puertos 8000 (Gunicorn),
9000 (MinIO), 5432 (PostgreSQL) y 6379 (Redis) al mundo, solo exponemos el 443
(y el 80 para redirigir a 443). Todo lo demás vive en la red interna de Docker,
invisible desde fuera. Un atacante no puede atacar lo que no puede ver.

### Por qué Gunicorn está detrás de Nginx

Gunicorn no debería estar expuesto directamente a Internet porque:

- No maneja SSL.
- No está diseñado para gestionar conexiones lentas (un cliente con conexión lenta
  puede mantener un worker ocupado durante segundos sin hacer nada útil — ataque
  slowloris). Nginx es experto en esto.
- No sirve archivos estáticos eficientemente.

En `docker-compose.prod.yml`, el servicio `web` no tiene `ports:` declarados.
Solo la red interna de Docker puede hablar con él. El único que tiene acceso
es Nginx, que sí está expuesto (`ports: ["80:80", "443:443"]`).

### Por qué los archivos estáticos de Django van a través de Nginx de todas formas

En `nginx/nginx.conf` hay un bloque `location /static/` que hace `proxy_pass
http://web:8000`. Espera — ¿no dijimos que los estáticos no deberían pasar por
Gunicorn?

La razón es que en este setup Docker, los archivos estáticos se generan con
`collectstatic` dentro del contenedor `migrate` y quedan en el volumen interno
de la imagen de `web`. Para que Nginx los sirva directamente necesitaría acceso
a ese directorio (con un volumen compartido). Por simplicidad en este setup de
portafolio, Nginx los reenvía a Gunicorn en lugar de montar un volumen extra.

En una arquitectura más avanzada se usaría un volumen compartido entre `web` y
`nginx` para que Nginx sirva `/static/` directamente. Es una mejora de
rendimiento que puedes añadir en Fase 6.

---

## 3. Multi-stage Dockerfiles — por qué dos stages

Ambos Dockerfiles (`backend/Dockerfile` y `frontend/Dockerfile`) usan un patrón
llamado **multi-stage build**. Hay dos stages: `builder` y `runtime` (o
`production`). Entender por qué es importante para entender tanto el tamaño de
las imágenes como la seguridad.

### El problema con un solo stage

Si usaras un único stage para el backend:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", ...]
```

La imagen resultante incluiría: `pip`, el caché de compilación de paquetes C
(algunos paquetes Python tienen extensiones en C que se compilan al instalarse),
`gcc`, headers del sistema, y todo lo que `pip` descargó durante la instalación.
Nada de eso es necesario para correr la aplicación; solo fue necesario para
compilarla.

Una imagen de producción de Django con este enfoque puede pesar 800 MB — 1 GB.

### Cómo funciona multi-stage

Con dos stages, el segundo stage empieza desde cero (`FROM python:3.13-slim AS
runtime`) y solo copia lo que necesita del primero:

```dockerfile
# Stage 1: builder — instala dependencias, puede pesar lo que quiera
FROM python:3.13-slim AS builder
WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime — imagen final, solo lo necesario para correr
FROM python:3.13-slim AS runtime
WORKDIR /app
# Dependencias de sistema en runtime (libmagic, tesseract, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 tesseract-ocr tesseract-ocr-spa poppler-utils \
    && rm -rf /var/lib/apt/lists/*
# Solo los paquetes Python instalados, no las herramientas de build
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Código fuente
COPY . .
```

La imagen final (`runtime`) no contiene `pip`, ni `gcc`, ni caché de build.
Solo contiene:
- La instalación base de Python (`python:3.13-slim`).
- Los paquetes del sistema necesarios en runtime: `libmagic1` (detección de
  tipo de archivo por magic bytes), `tesseract-ocr` + `tesseract-ocr-spa` (OCR
  en español/inglés), `poppler-utils` (conversión PDF→imagen para el OCR).
- Los paquetes Python ya instalados (copiados del builder).
- El código fuente de SasVault.

La diferencia de tamaño es sustancial: la imagen del builder puede pesar 1 GB;
la imagen de runtime queda en torno a 300-400 MB.

### El usuario no-root y por qué importa

Al final del `backend/Dockerfile`:

```dockerfile
RUN useradd --create-home appuser
USER appuser
```

Por defecto, los contenedores Docker corren como `root` dentro del contenedor.
Si la aplicación tiene una vulnerabilidad que permite ejecutar comandos
arbitrarios (por ejemplo, un bug de path traversal en la subida de archivos),
un atacante que la explote obtiene privilegios de root dentro del contenedor.

Aunque el contenedor está aislado del host, los privilegios de root facilitan
escapar del aislamiento (container escape) mediante otras vulnerabilidades del
kernel o del runtime Docker.

Corriendo como `appuser` (un usuario sin privilegios), el atacante que comprometa
la aplicación obtiene acceso muy limitado: no puede instalar binarios, no puede
leer archivos del sistema fuera de `/home/appuser`, no puede escalar privilegios
directamente.

Es una capa adicional de defensa. La regla del menor privilegio: da a cada
proceso exactamente los permisos que necesita para funcionar y nada más.

### El frontend: de Node a Nginx

El `frontend/Dockerfile` sigue el mismo principio pero con tecnologías distintas:

```dockerfile
# Stage 1: builder — Node.js compila el SPA
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build   # genera /app/dist con HTML + JS + CSS minificados

# Stage 2: production — Nginx sirve los estáticos
FROM nginx:stable-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
```

El stage `builder` usa Node.js (un runtime de JavaScript), npm, y todas las
herramientas de Vite. El stage final es solo Nginx con los archivos compilados.
Node.js no aparece en la imagen de producción: no lo necesitamos, el código ya
está compilado.

La imagen final del frontend pesa alrededor de 25-30 MB — Nginx Alpine es
diminuto.

---

## 4. docker-compose.prod.yml — los 8 servicios

El archivo `docker-compose.prod.yml` orquesta todos los procesos de SasVault
como contenedores coordinados. Es el equivalente de "arrancar el servidor", pero
de forma declarativa y reproducible.

Estos son los 8 servicios y por qué existe cada uno.

### `migrate` — el servicio que corre primero y muere

```yaml
migrate:
  command: >
    sh -c "python manage.py migrate --noinput &&
           python manage.py collectstatic --noinput"
  restart: "no"
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

`migrate` tiene un trabajo especial: preparar la base de datos antes de que
cualquier otro servicio empiece. Corre `migrate` (aplica migraciones pendientes)
y `collectstatic` (copia todos los archivos estáticos de Django a un directorio
unificado), luego **sale con código 0**.

**Por qué es un servicio separado y no parte de `web`:**

Imagina que en vez de esto, el `command` del servicio `web` fuera:
```
sh -c "python manage.py migrate && gunicorn ..."
```

Ahora `worker` y `beat` también arrancan a la vez que `web`, y cada uno podría
intentar correr migraciones simultáneamente. Si tres procesos intentan aplicar
la misma migración a la vez en PostgreSQL, obtienes:
- Race conditions: dos procesos ven la misma migración como "no aplicada" y
  ambos intentan aplicarla.
- Lock de tabla: Django adquiere un lock durante las migraciones; los otros
  procesos esperan bloqueados.
- Errores difíciles de diagnosticar en el primer boot.

Al tener `migrate` como un servicio separado con `restart: "no"`, garantizamos
que el proceso de migración ocurre exactamente una vez, de forma serial, antes
de que cualquier otro proceso empiece.

**El `condition: service_completed_successfully` es clave:**

```yaml
web:
  depends_on:
    migrate:
      condition: service_completed_successfully
```

Esto le dice a Docker Compose: "No arranques `web` hasta que `migrate` haya
terminado con código de salida 0". Si las migraciones fallan (error de conexión,
migración con error SQL), `migrate` sale con código no-0, y `web`, `worker` y
`beat` nunca arrancan. Ves el error en los logs de `migrate` y lo corriges antes
de que la aplicación esté parcialmente en un estado inconsistente.

Compara esto con `condition: service_started` (que solo espera a que el
contenedor arranque) o sin `condition` (que no espera nada). El
`service_completed_successfully` es la forma correcta.

### `web` — Django sirviendo requests de API

```yaml
web:
  command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
  restart: unless-stopped
```

El servicio central. Arranca Gunicorn con 2 workers. No tiene `ports:` en el
compose — no está expuesto al exterior. Solo Nginx puede hablar con él a través
de la red interna de Docker.

`restart: unless-stopped` significa: si el contenedor muere (crash, OOM,
error no capturado), Docker lo reinicia automáticamente. La única forma de que
no se reinicie es que lo pares explícitamente con `docker compose stop`.

### `worker` — Celery procesando tareas en segundo plano

```yaml
worker:
  command: celery -A config.celery worker --loglevel=info
  restart: unless-stopped
```

`worker` es el proceso que consume las tareas que Django encola en Redis.
En SasVault maneja: OCR de documentos (`process_ocr`), análisis de IA con
Claude (`analyze`), y envío de notificaciones (`send_notification`).

Sin `worker`, las tareas se encolan en Redis pero nadie las procesa. Los
documentos subidos quedarían con `ocr_status=pending` para siempre.

`worker` y `web` son procesos completamente independientes. `web` recibe el
request HTTP, encola la tarea en Redis, y responde inmediatamente (202 Accepted).
`worker` toma la tarea de Redis cuando tiene capacidad y la procesa. Esta
separación es lo que hace que la API sea rápida y responsive aunque el OCR tarde
30 segundos.

### `beat` — el cron de Celery

```yaml
beat:
  command: celery -A config.celery beat --loglevel=info
  restart: unless-stopped
```

`beat` es el scheduler de Celery: dispara tareas periódicas según el calendario
definido en `CELERY_BEAT_SCHEDULE` (en `backend/config/settings/base.py`).

En SasVault, la tarea `cleanup_orphan_blobs` corre diariamente a las 03:00 UTC:
recorre MinIO, encuentra blobs que ya no tienen un documento asociado en la base
de datos, y los elimina si llevan más de 24 horas (período de gracia).

**Importante:** `beat` y `worker` son procesos separados. `beat` solo genera
las tareas (las encola en Redis); `worker` las ejecuta. Nunca corras dos
instancias de `beat` simultáneamente — duplicarías las ejecuciones.

### `postgres` — la base de datos con volumen persistente

```yaml
postgres:
  image: postgres:16-alpine
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-saasvault_user} -d ${DB_NAME:-saasvault_prod}"]
    interval: 10s
    timeout: 5s
    retries: 5
```

El volumen nombrado `postgres_data:/var/lib/postgresql/data` es lo más crítico
de esta configuración. Entiéndelo bien.

**Qué es un volumen nombrado:**

Un contenedor Docker es efímero por naturaleza. Cuando lo destruyes y lo recreas
(lo que hace `deploy.sh` en cada deploy), su sistema de archivos interno
desaparece. Si PostgreSQL guardara sus datos en el sistema de archivos del
contenedor, perderías toda la base de datos en cada deploy.

Un volumen nombrado (`postgres_data`) es un directorio en el host del VPS
(generalmente bajo `/var/lib/docker/volumes/`) que Docker monta dentro del
contenedor en la ruta que especifiques. Cuando el contenedor muere y nace uno
nuevo, el volumen sigue ahí, con todos los datos intactos. El nuevo contenedor
lo monta y PostgreSQL lo encuentra exactamente como lo dejó.

Nunca hagas esto en producción:

```yaml
# MAL — datos en el sistema de archivos del contenedor
postgres:
  image: postgres:16-alpine
  # Sin volumes: los datos mueren con el contenedor
```

Siempre usa un volumen nombrado para PostgreSQL, Redis, y MinIO.

**El healthcheck:**

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U saasvault_user -d saasvault_prod"]
  interval: 10s
  timeout: 5s
  retries: 5
```

`pg_isready` es una herramienta de PostgreSQL que devuelve éxito solo cuando
el servidor está listo para aceptar conexiones. Esto es lo que hace posible el
`condition: service_healthy` de `migrate` y `web`: Docker espera hasta que el
healthcheck pase antes de arrancar los servicios dependientes.

Sin healthcheck, Docker arranca los servicios dependientes cuando el contenedor
`postgres` empieza (que es mucho antes de que PostgreSQL esté listo para
conexiones), y obtienes errores de conexión al arrancar.

### `redis` — el intermediario de mensajes

```yaml
redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```

Redis cumple tres funciones en SasVault (separadas en tres bases de datos
numeradas 0, 1, 2):

- **DB 0 (`REDIS_URL`):** caché de Django (resultados de consultas frecuentes,
  datos de sesión).
- **DB 1 (`CELERY_BROKER_URL`):** broker de Celery. Las tareas encoladas por
  Django viven aquí hasta que `worker` las consume.
- **DB 2 (`CELERY_RESULT_BACKEND`):** resultados de tareas Celery. Cuando
  `worker` termina una tarea, guarda el resultado (o el error) aquí para que
  `web` pueda consultarlo si lo necesita.

Usar tres DBs en vez de una sola es una buena práctica porque así puedes hacer
`FLUSHDB` en la caché sin borrar el broker, y puedes configurar expiración y
persistencia diferente para cada uno.

### `minio` — almacenamiento de archivos compatible con S3

```yaml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  volumes:
    - minio_data:/data
```

MinIO es un servidor de almacenamiento de objetos compatible con la API de
Amazon S3. En desarrollo se usa para que el código que interactúa con S3 funcione
sin depender de AWS. En producción (de portafolio), lo usamos igual.

El `StorageService` de SasVault usa `boto3` (la librería oficial de AWS) para
hablar con MinIO exactamente igual que hablaría con S3 real — solo cambia el
endpoint.

El volumen `minio_data:/data` guarda los blobs de los documentos subidos. Sin
él, todos los archivos subidos desaparecerían en cada deploy.

Para producción real con usuarios reales, lo que conviene es apuntar a S3 real:
más durabilidad, CDN, y no tienes que gestionar el disco del VPS. Cambiar
requiere solo actualizar variables de entorno.

### `nginx` — el gateway

```yaml
nginx:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    target: production
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./nginx/certs:/etc/nginx/certs:ro
```

El servicio `nginx` está construido desde el `Dockerfile` del frontend
(`target: production` selecciona el stage `FROM nginx:stable-alpine`), que ya
incluye los archivos compilados del SPA. El `nginx.conf` se monta desde el host
(`:ro` = read-only, solo lectura), igual que los certificados SSL.

Este es el único servicio con `ports:` expuestos al exterior: 80 y 443.

### Los volúmenes nombrados

Al final de `docker-compose.prod.yml`:

```yaml
volumes:
  postgres_data:
  redis_data:
  minio_data:
```

Esta declaración le dice a Docker Compose que cree estos volúmenes si no
existen. Docker los gestiona y persiste entre reinicios de contenedores y
deploys. **Nunca se borran automáticamente** — tienes que borrarlos
explícitamente con `docker volume rm` si quieres eliminarlos (con toda la
pérdida de datos que eso implica).

---

## 5. Nginx — el guardián de la puerta

El archivo `nginx/nginx.conf` tiene dos bloques `server`. Leámoslos
cuidadosamente.

### Bloque 1: Redirección HTTP → HTTPS

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
```

Cualquier petición que llegue por el puerto 80 (HTTP) recibe una redirección
permanente (301) a la misma URL pero con HTTPS. El código 301 le dice al
navegador "esto ya no está aquí, ve allá para siempre", y el navegador recuerda
el redirect en caché — las visitas futuras ya van directo al 443.

Por qué es obligatorio y no opcional:
- HTTP transmite datos en texto plano. En una red WiFi pública, cualquiera con
  Wireshark puede ver los tokens JWT, las contraseñas, los documentos. HTTPS
  cifra todo.
- Los navegadores modernos marcan las páginas HTTP como "No seguro".
- Google penaliza en SEO a sitios sin HTTPS.
- Las cookies con `Secure=True` (que Django configura en producción) no se
  envían por HTTP — la app dejaría de funcionar.

### Bloque 2: El servidor HTTPS

```nginx
server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/nginx/certs/selfsigned.crt;
    ssl_certificate_key /etc/nginx/certs/selfsigned.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ...
}
```

`ssl_protocols TLSv1.2 TLSv1.3` deshabilita versiones antiguas de TLS (1.0,
1.1) que tienen vulnerabilidades conocidas. `ssl_ciphers HIGH:!aNULL:!MD5`
prohíbe algoritmos de cifrado débiles.

### `try_files` — el truco para SPAs

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

Esta directiva es probablemente la más importante para que la aplicación React
funcione correctamente, y también una de las menos intuitivas.

**El problema:** React Router gestiona las rutas en el navegador (client-side
routing). Cuando el usuario navega de `/` a `/documents/123`, React intercepta
el click, actualiza la URL en la barra del navegador, y renderiza el componente
correcto — todo sin hacer una petición al servidor. Hasta aquí todo bien.

El problema ocurre cuando el usuario **recarga la página** estando en
`/documents/123`, o cuando alguien le manda el enlace directo. En ese caso,
el navegador hace una petición GET a `https://tudominio.com/documents/123`.
Nginx recibe esa petición y busca un archivo en disco en
`/usr/share/nginx/html/documents/123`. Ese archivo no existe (el directorio
`documents/` no existe; todo es `index.html` y los chunks JS de Vite). Sin
`try_files`, Nginx devuelve 404.

**La solución:** `try_files $uri $uri/ /index.html` le dice a Nginx:
1. Primero busca el archivo exacto (`$uri`): si alguien pide `/logo.svg`, lo
   sirve directamente desde el sistema de archivos.
2. Si no existe, busca el directorio (`$uri/`): si alguien pide `/assets/`,
   busca un `index.html` dentro.
3. Si tampoco existe, sirve `/index.html` — y React Router se encarga del resto.

En otras palabras: si el archivo existe físicamente (JS, CSS, imágenes), sírvelo.
Si no existe, sirve `index.html` y deja que React decida qué renderizar.

### `proxy_pass` — el reenvío a Django

```nginx
location /api/ {
    proxy_pass         http://web:8000;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
}
```

**Por qué `web` y no `localhost`:**

Dentro de Docker Compose, cada servicio tiene su propio hostname que corresponde
al nombre del servicio. `web` es el nombre del servicio de Gunicorn en el compose.
`localhost` dentro del contenedor de Nginx apunta al propio contenedor de Nginx,
no a Gunicorn. Docker tiene su propio DNS interno: cuando Nginx hace
`proxy_pass http://web:8000`, Docker resuelve `web` a la IP interna del
contenedor del servicio `web`. Es el DNS de Docker, no el DNS público de Internet.

**Los headers `proxy_set_header`:**

Nginx añade estos headers a cada petición que reenvía a Django:

- `Host: $host` — el hostname que el cliente original usó (tu dominio o IP).
  Django lo necesita para `ALLOWED_HOSTS` y para construir URLs absolutas.
- `X-Real-IP: $remote_addr` — la IP real del cliente. Sin esto, Django
  ve la IP del contenedor de Nginx como origen de todas las peticiones.
- `X-Forwarded-For: $proxy_add_x_forwarded_for` — la cadena de proxies por
  los que pasó la petición. Django la usa para logging y rate limiting.
- `X-Forwarded-Proto: $scheme` — el protocolo que el cliente usó (`https` o
  `http`). Este es el más crítico.

### `X-Forwarded-Proto` y el bug del loop infinito

Este es uno de los bugs de deploy más frecuentes, y entenderlo te ahorra horas.

En `backend/config/settings/production.py`:

```python
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

`SECURE_SSL_REDIRECT = True` le dice a Django: "si recibes una petición por
HTTP, redirige a HTTPS". Django determina si la petición es HTTP o HTTPS
mirando su propia conexión — que internamente siempre es HTTP (Nginx hace el
SSL y reenvía HTTP plano a Gunicorn).

Sin `SECURE_PROXY_SSL_HEADER`, Django ve HTTP en su conexión y redirige a
HTTPS. Nginx recibe HTTPS, la descifra, y reenvía HTTP a Django. Django ve
HTTP y redirige a HTTPS. Nginx... y así indefinidamente. El navegador del
usuario ve un error de "demasiados redirects" (ERR_TOO_MANY_REDIRECTS).

Con `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, Django
sabe que debe mirar el header `X-Forwarded-Proto` en vez de su propia
conexión. Si ese header dice `https`, Django considera la petición como segura.

El header `X-Forwarded-Proto: $scheme` que Nginx añade tiene el valor `https`
(porque el cliente vino por HTTPS). Django lo ve, dice "ok, esto es una petición
segura", y no redirige.

**Secuencia sin el fix:**
```
Cliente → HTTPS → Nginx → HTTP a Django (sin header)
Django: "esto es HTTP, redirijo a HTTPS" → 301
Cliente → HTTPS → Nginx → HTTP a Django
Django: "esto es HTTP, redirijo a HTTPS" → 301
... (bucle infinito)
```

**Secuencia con el fix:**
```
Cliente → HTTPS → Nginx → HTTP a Django + header X-Forwarded-Proto: https
Django: "el proxy dice que vino por HTTPS, está bien" → 200
```

---

## 6. Variables de entorno en producción — qué cambia y por qué

El archivo `backend/.env.production.example` es el template de configuración
para producción. Cópialo y rellénalo:

```bash
cp backend/.env.production.example backend/.env.production
```

Nunca commitees `backend/.env.production` a git — está en `.gitignore`.

Repasemos cada grupo de variables y por qué las de producción son distintas a
las de desarrollo.

### Django core

```dotenv
DJANGO_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<VPS_IP_or_domain>
```

**`DJANGO_SECRET_KEY`:** Django usa esta clave para firmar criptográficamente
todo lo que necesita ser a prueba de manipulación: tokens CSRF, cookies de
sesión, tokens de password reset, y parte de los JWT. Si un atacante conoce
tu `SECRET_KEY`, puede generar tokens válidos sin autenticarse. En desarrollo
es irrelevante (el servidor no está expuesto); en producción debe ser:
- Única (diferente a la de desarrollo y a cualquier otra instalación).
- Aleatoria (no una frase, no tu nombre, no un UUID predecible).
- Larga (al menos 50 caracteres).

Genérala con el comando del comentario:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Guárdala en `.env.production` y nunca la compartas ni la muestres en logs.

**`DJANGO_DEBUG=False`:** Con `DEBUG=True`, Django muestra tracebacks detallados
en el navegador, sirve archivos estáticos automáticamente (ignorando Nginx),
deshabilita algunas validaciones de seguridad, y guarda en memoria el historial
de todas las queries SQL para el toolbar de debug. Nada de eso debe ocurrir
en producción.

**`DJANGO_ALLOWED_HOSTS`:** Django rechaza peticiones cuyo header `Host` no
coincida con esta lista. Es una protección contra ataques de HTTP Host header
injection. Pon aquí la IP del VPS y/o el dominio que uses.

### Base de datos

```dotenv
DB_HOST=postgres
DB_PORT=5432
```

**Por qué `DB_HOST=postgres` y no `localhost`:**

La misma razón que `proxy_pass http://web:8000` en Nginx. Docker Compose crea
una red virtual para los servicios. Dentro de esa red, cada servicio es
accesible por su nombre. `postgres` es el nombre del servicio PostgreSQL en
`docker-compose.prod.yml`. Si pusieras `localhost`, Django buscaría PostgreSQL
en el propio contenedor de Django — donde no hay ningún PostgreSQL.

### Redis — tres bases de datos separadas

```dotenv
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

Redis tiene 16 bases de datos numeradas (0-15) dentro de la misma instancia.
Son independientes: puedes hacer `SELECT 1` para usar la DB 1, que tiene sus
propios keys sin conflicto con la DB 0.

Separar caché (0), broker (1) y results (2) tiene varias ventajas:
- Puedes limpiar la caché (`FLUSHDB 0`) sin afectar las tareas pendientes en
  el broker.
- Puedes configurar persistencia diferente: el broker necesita durabilidad
  (una tarea perdida es un proceso perdido), la caché puede ser volátil.
- Puedes monitorear cada uso por separado.

### MinIO

```dotenv
MINIO_ENDPOINT=minio:9000
MINIO_USE_SSL=False
```

**Por qué `minio` y no `localhost`:** mismo principio DNS de Docker que para
PostgreSQL.

**Por qué `MINIO_USE_SSL=False` en producción dockerizada:** El tráfico entre
el contenedor de Django (`web`) y el contenedor de MinIO (`minio`) nunca sale
de la red interna de Docker. No pasa por Internet. No necesita ser cifrado
porque es una red privada virtual. Añadir TLS aquí añadiría complejidad
(gestionar certificados internos) sin beneficio de seguridad real — el atacante
externo ya no puede ver ese tráfico.

El TLS lo termina Nginx para el tráfico exterior. El tráfico interno va sin
cifrar. Este es el patrón estándar.

### JWT

```dotenv
JWT_ACCESS_LIFETIME_MIN=15
```

En desarrollo, `JWT_ACCESS_LIFETIME_MIN=60` (60 minutos) — así no tienes que
re-autenticarte cada vez que dejas de trabajar. En producción, 15 minutos. Por
qué el tiempo importa:

Un access token JWT no puede invalidarse antes de que expire (no hay un sistema
de "log out server-side" para tokens sin estado, salvo la blacklist de refresh
tokens). Si un atacante roba un access token, tiene acceso a la cuenta durante
el tiempo de vida del token. 15 minutos limita la ventana de ataque.

El refresh token dura 7 días y sí está en la blacklist — si lo robas,
el usuario puede revocar todas las sesiones.

### Sentry

```dotenv
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
```

Dejar `SENTRY_DSN` vacío deshabilita el error tracking completamente (ver
`production.py`: `if SENTRY_DSN: sentry_sdk.init(...)`). Para habilitar Sentry:
1. Crea una cuenta en sentry.io (tiene plan gratuito).
2. Crea un proyecto Django.
3. Copia el DSN que te dan.
4. Pégalo en `.env.production`.

Sentry captura cada excepción no manejada, con traceback, contexto de la
petición, y metadata útil. Es la diferencia entre "algo falló en producción"
y "sabes exactamente qué, dónde, con qué datos".

La función `_scrub_sensitive_headers` en `production.py` borra el header
`Authorization` y el body de las peticiones a `/auth/` antes de enviarlas a
Sentry. Nunca envíes contraseñas ni tokens a servicios de terceros.

### Variables opcionales para features

```dotenv
ANTHROPIC_API_KEY=
SENDGRID_API_KEY=
```

SasVault está diseñado con feature flags: si estas variables están vacías, las
features están desactivadas. El endpoint `POST /api/v1/documents/{id}/analyze/`
devuelve 503 si `ANTHROPIC_API_KEY` está vacío. Las notificaciones por email
fallan silenciosamente si `SENDGRID_API_KEY` está vacío. Puedes desplegar
sin estas features y activarlas cuando las necesites sin tocar código.

---

## 7. El certificado SSL — autofirmado vs real

Para entender el SSL/TLS necesitas un modelo mental claro.

### Qué es TLS

Cuando un navegador y un servidor establecen una conexión HTTPS, primero
hacen un "handshake": negocian una clave de cifrado que solo ellos conocen,
usando criptografía asimétrica. Después de eso, toda la comunicación va cifrada
con esa clave. Un tercero que capture el tráfico solo ve ruido.

La analogía: es como enviar cartas en una caja con candado combinado. El
cartero (Internet) lleva la caja pero no puede abrirla. Solo el remitente y
el destinatario tienen la combinación.

### Qué es un certificado

El certificado es el mecanismo por el que el navegador verifica que está hablando
con quien dice ser. Contiene:
- La clave pública del servidor.
- El dominio para el que fue emitido.
- La firma de una Autoridad Certificadora (CA) que garantiza que la información
  es correcta.

Cuando tu navegador ve `https://banco.com`, pide el certificado. Verifica que
fue emitido para `banco.com` y que la firma pertenece a una CA de confianza
(la lista está preinstalada en tu sistema operativo y navegador). Si todo
cuadra, el candado verde aparece.

### Qué es un certificado autofirmado

Un certificado autofirmado es uno donde tú mismo eres la CA. Técnicamente
funciona igual para cifrar la comunicación, pero el navegador no puede
verificar que fuiste tú quien lo firmó — y no que un atacante que interceptó
la conexión lo firmó haciéndose pasar por ti.

El script `scripts/deploy.sh` genera uno automáticamente:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/certs/selfsigned.key \
    -out nginx/certs/selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=SasVault/CN=localhost"
```

El resultado: el navegador muestra un aviso de "conexión no segura" y el usuario
tiene que aceptar explícitamente. En un demo de portafolio esto es aceptable.
En una aplicación con usuarios reales, no.

Analogía: un certificado autofirmado es como hacerte tu propio DNI. Técnicamente
es un documento de identidad, pero ningún banco ni aeropuerto lo acepta porque
no hay ninguna entidad de confianza que respalde que eres quien dices ser.

### Qué es Let's Encrypt

Let's Encrypt es una Autoridad Certificadora gratuita y automatizada, operada
por una organización sin ánimo de lucro (ISRG). Emite certificados de dominio
válidos que los navegadores aceptan sin aviso.

Funciona con el protocolo ACME: tu servidor demuestra que controlas el dominio
respondiendo a un challenge HTTP (Let's Encrypt llama a una URL específica en
tu dominio y verifica la respuesta). Si el challenge pasa, emite el certificado.
El certificado dura 90 días y se renueva automáticamente.

Para obtener uno:

```bash
# Instalar certbot en el VPS
sudo apt install certbot python3-certbot-nginx

# Obtener certificado (cambia example.com por tu dominio real)
sudo certbot --nginx -d example.com

# Certbot modifica nginx.conf automáticamente y añade el certificado
```

Para usar el certificado real con este setup:

1. Para el servicio Nginx: `docker compose -f docker-compose.prod.yml stop nginx`
2. Reemplaza `nginx/certs/selfsigned.crt` con el certificado de Let's Encrypt
   (en `/etc/letsencrypt/live/tudominio/fullchain.pem`).
3. Reemplaza `nginx/certs/selfsigned.key` con la clave privada
   (en `/etc/letsencrypt/live/tudominio/privkey.pem`).
4. Arranca Nginx: `docker compose -f docker-compose.prod.yml start nginx`

Let's Encrypt es apropiado para cualquier sitio público con un dominio real.
El certificado autofirmado es apropiado para portafolios, demos internos, y
entornos de desarrollo donde el aviso del navegador no importa.

---

## 8. Scripts de deploy y backup

### deploy.sh — el flujo paso a paso

El script `scripts/deploy.sh` es idempotente: puedes ejecutarlo diez veces
seguidas y el resultado final es el mismo que ejecutarlo una vez.

**Idempotente** significa que la operación puede repetirse sin efectos
secundarios. Es crucial en deploy porque los scripts fallan a mitad de
ejecución, se cuelgan, o los corres dos veces por error. Si tu script es
idempotente, puedes rerrunner sin miedo.

Repasemos cada paso:

#### `set -euo pipefail`

Esta es la primera línea ejecutable del script. Sin ella, bash por defecto:
- Continúa ejecutando comandos aunque uno falle (el `e` lo previene: "exit
  on error").
- Usa variables no definidas como strings vacíos silenciosamente (el `u` lo
  previene: "unset variable = error").
- Considera que un pipe (`cmd1 | cmd2`) falla solo si el último comando falla,
  ignorando errores en `cmd1` (el `pipefail` lo previene).

Ejemplo de por qué importa:

```bash
# Sin set -euo pipefail
git pull origin main        # falla porque no tienes internet
docker compose build        # continúa igualmente — construye la imagen VIEJA
docker compose up -d        # despliega código VIEJO sin error visible
```

Con `set -euo pipefail`, el script para en la primera línea que falla y muestra
el error. Nadie acaba con código viejo en producción silenciosamente.

#### Paso 1: `git pull origin main`

Descarga los últimos commits del branch `main`. El VPS siempre tiene el repo
clonado y este paso actualiza el código local.

#### Paso 2: Generación del certificado autofirmado (si no existe)

```bash
if [ ! -f "$CERTS_DIR/selfsigned.crt" ]; then
    openssl req -x509 ...
fi
```

El `if [ ! -f ... ]` hace esto idempotente: si el certificado ya existe, salta
la generación. Así no lo regenera en cada deploy (lo que invalidaría el cert
anterior). Si quieres regenerarlo, bórralo manualmente primero.

#### Paso 3: `docker compose -f docker-compose.prod.yml build`

Reconstruye las imágenes Docker de todos los servicios. Como el `Dockerfile`
del backend tiene `COPY . .`, cualquier cambio en el código queda incorporado
en la nueva imagen.

Docker usa caché de capas: si `requirements.txt` no cambió, no reinstala las
dependencias. Si solo cambió el código Python (que viene después del
`pip install`), reconstruye solo desde esa capa. Los deploys sin cambios de
dependencias son rápidos.

#### Paso 4: `docker compose -f docker-compose.prod.yml run --rm migrate`

Corre el servicio `migrate` y lo elimina al terminar (`--rm`). Aplica
migraciones pendientes y ejecuta `collectstatic`.

Si hay 0 migraciones pendientes, `migrate` sale con código 0 igualmente — es
idempotente. Si hay 5 migraciones, las aplica en orden.

#### Paso 5: `docker compose -f docker-compose.prod.yml up -d`

Arranca o recrea todos los servicios en segundo plano (`-d` = detached). Si un
servicio ya estaba corriendo con una imagen vieja, Docker Compose lo recrea con
la nueva imagen construida en el paso 3. Si estaba detenido, lo arranca.

La secuencia de arranque respeta los `depends_on`: `postgres` y `redis`
arrancan primero, luego `migrate` espera el healthcheck de ambos, luego `web`,
`worker`, `beat`, y `nginx` esperan a que `migrate` complete exitosamente.

#### Paso 6: `docker image prune -f`

Borra imágenes Docker que ya no son usadas por ningún contenedor. Cada deploy
crea nuevas imágenes; las anteriores quedan huérfanas. En un VPS con disco
limitado, esto evita que Docker consuma todo el espacio en semanas.

#### Cómo usar el script

```bash
# En el VPS, una vez que el repo está clonado
ssh usuario@tu-vps-ip
cd /opt/saasvault
bash scripts/deploy.sh
```

O si configuraste el workflow de GitHub Actions, desde cualquier lugar:
ir a GitHub → Actions → "Deploy to VPS" → Run workflow → production.

### backup_db.sh — por qué pg_dump y no copiar archivos

Este es un error que mucha gente comete cuando empieza con bases de datos: "voy
a hacer un backup copiando el directorio de datos de PostgreSQL". No funciona.

**Por qué no puedes copiar el data directory de PostgreSQL en caliente:**

PostgreSQL no escribe datos a disco en el momento exacto en que confirmas una
transacción. Usa un mecanismo llamado WAL (Write-Ahead Log) donde los cambios
se escriben primero en un log y se aplican al data directory de forma asíncrona.
En cualquier momento dado, el data directory puede estar en un estado
"entre transacciones": algunas transacciones están escritas en el WAL pero
no en los archivos de datos; otras en ambos.

Si copias el directorio mientras PostgreSQL está corriendo, obtienes una copia
de un estado inconsistente: algunas transacciones a medias, archivos con
referencias a páginas que no existen aún, etc. Al intentar restaurar, PostgreSQL
no puede arrancar o la base de datos tiene datos corruptos.

**Qué hace `pg_dump`:**

`pg_dump` hace una "dump lógica": conecta a PostgreSQL como cliente y extrae
los datos mediante queries SQL. PostgreSQL le garantiza una vista consistente
del estado de la base de datos en el momento en que empieza el dump (usando
transacciones con aislamiento serializable). El resultado es un archivo `.sql`
con instrucciones `CREATE TABLE`, `INSERT`, `COPY`, etc. que reproducen el estado
de la base de datos fielmente.

Esto funciona incluso con la base de datos activa y con usuarios conectados.
El dump es una foto consistente del instante en que empezó.

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U saasvault_user saasvault_prod \
    | gzip > "$BACKUP_FILE"
```

`exec -T postgres` ejecuta el comando dentro del contenedor de PostgreSQL sin
asignar una terminal interactiva (necesario para que el pipe funcione en scripts).
`| gzip` comprime el output al vuelo — un dump de 500 MB puede quedar en 50 MB.

El script guarda el backup en `/var/backups/saasvault/` con un timestamp:
`saasvault_20260629_030000.sql.gz`.

**Retención de 7 días:**

```bash
find "$BACKUP_DIR" -name "saasvault_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
```

Borra los backups de más de 7 días. Si necesitas más retención, cambia
`RETENTION_DAYS`. El equilibrio es entre espacio en disco y cobertura ante
desastres — 7 días cubre la mayoría de los casos (si notas un problema el
martes, probablemente tienes un backup del viernes anterior que es anterior
al problema).

**Automatización con crontab:**

```bash
# En el VPS, editarlo con: crontab -e
# Ejecuta el backup cada día a las 02:00
0 2 * * * cd /opt/saasvault && bash scripts/backup_db.sh >> /var/log/saasvault-backup.log 2>&1
```

`>> /var/log/saasvault-backup.log 2>&1` redirige tanto la salida estándar como
los errores al log. Puedes revisar el historial con `tail -n 50
/var/log/saasvault-backup.log`.

**Cómo restaurar:**

```bash
# Descomprimir e insertar en la base de datos activa
gunzip -c /var/backups/saasvault/saasvault_20260629_030000.sql.gz \
    | docker compose -f docker-compose.prod.yml exec -T postgres \
        psql -U saasvault_user saasvault_prod
```

Esto inserta los datos del backup en la base de datos actual. Si quieres
empezar desde cero:

```bash
# Borrar la base de datos y recrearla vacía antes de restaurar
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U saasvault_user -c "DROP DATABASE saasvault_prod; CREATE DATABASE saasvault_prod;"
# Luego la restauración de arriba
```

---

## 9. Cómo diagnosticar fallos comunes

Los problemas de deploy casi siempre caen en un conjunto predecible de
categorías. Aquí están los más frecuentes, sus causas probables, y cómo
investigarlos.

El comando más usado para diagnóstico es siempre:

```bash
docker compose -f docker-compose.prod.yml logs <servicio>
# O para ver los últimos N líneas en tiempo real:
docker compose -f docker-compose.prod.yml logs -f --tail=100 <servicio>
```

### Tabla de síntomas y diagnóstico

| Síntoma | Causa probable | Cómo investigar |
|---------|---------------|-----------------|
| `502 Bad Gateway` desde Nginx | Gunicorn no arrancó o crasheó | `docker compose -f docker-compose.prod.yml logs web` |
| Admin CSS no carga | `collectstatic` no corrió, o Nginx no sirve `/static/` correctamente | `logs migrate`; revisar `nginx.conf` el bloque `/static/` |
| Loop infinito de redirects (`ERR_TOO_MANY_REDIRECTS`) | Falta `SECURE_PROXY_SSL_HEADER` en `production.py`, o `X-Forwarded-Proto` no llega de Nginx | Revisar `production.py`; `logs web` buscando redirect 301 repetidos |
| `django.db.OperationalError: could not connect to server` al arrancar | `migrate` no terminó antes que `web`, o PostgreSQL todavía levantando | `logs migrate`; `logs postgres`; revisar `depends_on` en compose |
| Celery no procesa tareas (documentos en `ocr_status=pending` para siempre) | `CELERY_BROKER_URL` incorrecto, Redis caído, o `worker` nunca arrancó | `logs worker`; `docker compose exec redis redis-cli ping` |
| MinIO devuelve `NoSuchBucket` al subir archivos | El bucket no fue creado después de levantar MinIO | Ver sección "Creación del bucket MinIO" abajo |
| Archivos del frontend devuelven 404 | `npm run build` falló en el Dockerfile del frontend | Construir manualmente: `docker build -f frontend/Dockerfile . 2>&1` |
| `400 Bad Request` en todas las peticiones de API | `DJANGO_ALLOWED_HOSTS` no incluye el dominio/IP del VPS | Revisar `.env.production`; `logs web` buscando "Invalid HTTP_HOST" |
| Aplicación carga pero el login falla con `CORS error` | `CORS_ALLOWED_ORIGINS` no incluye el origin del frontend | `logs web`; revisar `.env.production` |
| Los tests de CI pasan pero la app falla en producción | Variable de entorno ausente en `.env.production` | `logs web` buscando `ImproperlyConfigured` o `KeyError` |
| `Permission denied` al escribir archivos | El contenedor corre como `appuser` pero el directorio tiene ownership de root | `docker compose exec web ls -la /app/` |

### Cómo ver el estado de todos los servicios

```bash
docker compose -f docker-compose.prod.yml ps
```

La columna `Status` te dice si el servicio está `Up`, `Exited`, o
`(unhealthy)`. Un servicio `Exited` casi siempre indica un error al arrancar;
revisa sus logs.

### Creación del bucket de MinIO

MinIO crea el directorio de datos al arrancar, pero no crea buckets
automáticamente. Si `MINIO_BUCKET_NAME=saasvault-prod` pero el bucket no
existe, el `StorageService` falla con `NoSuchBucket` al intentar subir el
primer archivo.

Crea el bucket después del primer `docker compose up`:

```bash
# Entrar al contenedor de MinIO
docker compose -f docker-compose.prod.yml exec minio sh

# Dentro del contenedor, usar el cliente mc de MinIO
mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
mc mb local/saasvault-prod
exit
```

O desde el host, si tienes el cliente `mc` instalado:

```bash
mc alias set prod http://TU_VPS_IP:9000 TU_ACCESS_KEY TU_SECRET_KEY
mc mb prod/saasvault-prod
```

También puedes usar la consola web de MinIO accesible en `http://TU_VPS_IP:9001`
(el puerto 9001 está expuesto en `docker-compose.prod.yml` como parte del
servicio minio).

### El deploy del workflow de GitHub Actions

El archivo `.github/workflows/deploy.yml` dispara el deploy remotamente:

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        required: true
        default: "production"
```

`workflow_dispatch` significa que se dispara manualmente desde la UI de GitHub
(no automáticamente en cada push). Para usarlo:

1. Ve a tu repositorio en GitHub → Actions → "Deploy to VPS".
2. Haz click en "Run workflow" → selecciona `production` → "Run workflow".
3. GitHub Actions se conecta al VPS por SSH usando las secrets `VPS_HOST`,
   `VPS_USER`, y `VPS_SSH_KEY`, y ejecuta `bash scripts/deploy.sh` en el VPS.

Para configurar las secrets:
- Ve a Settings → Secrets and variables → Actions → New repository secret.
- `VPS_HOST`: la IP del VPS.
- `VPS_USER`: el usuario SSH (típicamente `ubuntu` o `root`).
- `VPS_SSH_KEY`: la clave privada SSH que tiene acceso al VPS (el contenido del
  archivo `~/.ssh/id_rsa` o equivalente).

El workflow de CI (`.github/workflows/ci.yml`) corre automáticamente en cada
pull request y push a `main` o `develop`, ejecutando tests de backend y frontend.
Usa servicios efímeros de PostgreSQL y Redis — mismos que usamos localmente,
para garantizar que los tests siempre corren contra PostgreSQL real (no SQLite).

---

## 10. Glosario

Términos que aparecen en esta fase, explicados en 2-3 líneas.

**WSGI (Web Server Gateway Interface)**
El estándar Python que define cómo un servidor web (Gunicorn) habla con una
aplicación web (Django). Es el "enchufé" entre ambos. Análogo a ASGI pero
síncrono. Todos los frameworks Python web lo implementan.

**Reverse proxy**
Un servidor que recibe peticiones de los clientes y las reenvía a uno o más
servidores backend. El cliente nunca habla directamente con el backend. Nginx
actúa como reverse proxy para Gunicorn: el cliente ve Nginx, no le importa
ni sabe que Gunicorn existe.

**SSL/TLS termination**
El proceso de descifrar una conexión HTTPS en el proxy y reenviar HTTP plano
al backend. "Terminar" el SSL significa ser el último punto que trabaja con
el cifrado. Nginx termina el TLS; Gunicorn recibe HTTP sin cifrado, dentro
de la red privada de Docker.

**Multi-stage build**
Un Dockerfile con múltiples instrucciones `FROM`. Cada stage puede usar una
imagen base diferente. Los stages anteriores solo sirven para construir; el
stage final contiene solo lo necesario para correr. Resultado: imágenes
más pequeñas y sin herramientas de build que podrían ser vectores de ataque.

**Named volume**
Un volumen Docker gestionado por Docker (no un bind mount al sistema de archivos
del host). Persiste entre reinicios y recreaciones de contenedores. Es la única
forma correcta de persistir datos de bases de datos en Docker.

**Health check**
Un comando que Docker ejecuta periódicamente dentro de un contenedor para
verificar que el servicio está listo. Si el health check falla N veces seguidas,
el contenedor se marca como `unhealthy`. Los `depends_on: condition:
service_healthy` esperan a que el health check pase antes de arrancar servicios
dependientes.

**Idempotency (idempotencia)**
Una operación es idempotente si ejecutarla múltiples veces produce el mismo
resultado que ejecutarla una vez. Los scripts de deploy deben ser idempotentes:
si fallas a la mitad y reejecutas, no debes tener datos duplicados, servicios
rotos, o estados inconsistentes.

**HSTS (HTTP Strict Transport Security)**
Un header HTTP que le dice al navegador "este sitio SIEMPRE usa HTTPS; en los
próximos N segundos, no intentes conectarte por HTTP". Con `SECURE_HSTS_SECONDS
= 31536000` (1 año) y `SECURE_HSTS_PRELOAD = True` en `production.py`, los
navegadores que hayan visitado el sitio nunca intentan HTTP, eliminando el
window de ataque de SSL-stripping.

**CSP (Content Security Policy)**
Un header HTTP que le dice al navegador qué recursos puede cargar y de qué
orígenes. Sin CSP, un atacante que logre inyectar HTML en la página puede
cargar scripts maliciosos de dominios externos. SasVault no tiene CSP configurada
aún — es una mejora pendiente para Fase 6.

**CORS (Cross-Origin Resource Sharing)**
El mecanismo que controla qué dominios pueden hacer peticiones AJAX a tu API.
Sin CORS configurado, el navegador bloquea las peticiones del frontend a la API
si están en dominios distintos. `CORS_ALLOWED_ORIGINS` en `.env.production`
debe incluir el dominio exacto del frontend (incluido el protocolo: `https://`).

---

*Última actualización: 2026-06-29. Refleja la infraestructura de Fase 5.4 —
CI/CD + deploy a VPS.*
