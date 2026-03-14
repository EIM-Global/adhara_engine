# Dockerfile: Static Vite SPA served by nginx
#
# Multi-stage build: Node builds the static assets, nginx serves them.
#
# Usage:
#   docker build -t podcast-site .
#   docker run -p 3000:3000 podcast-site

# -- Stage 1: Build ----------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# -- Stage 2: Serve with nginx -----------------------------------------------
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# SPA-friendly nginx config: serves static files, falls back to index.html
RUN cat > /etc/nginx/conf.d/app.conf <<'EOF'
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    # Serve static assets with cache headers
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback — serve index.html for all non-file routes
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
