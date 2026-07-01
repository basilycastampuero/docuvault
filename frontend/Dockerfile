# ---- Stage 1: build ----
# Build the React/Vite SPA. Output lands in /app/dist.
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Allow overriding the API base URL at build time.
# Default is a same-origin relative path so the bundle works behind any domain
# without hardcoding a host (avoids the localhost:8000 fallback in development).
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---- Stage 2: production ----
# Nginx serves the compiled static files. The docker-compose.prod.yml mounts the
# site-specific nginx.conf, which handles SPA fallback and SSL termination.
FROM nginx:stable-alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
