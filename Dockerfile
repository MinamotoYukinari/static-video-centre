FROM nginx:1.27-alpine

WORKDIR /usr/share/nginx/html

# Copy static site assets. The media directory can be overridden by a bind mount in docker-compose.
COPY . .

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD wget -qO- http://127.0.0.1/index.html >/dev/null || exit 1
