# The site is plain HTML with no build step, so there is no build stage: copy
# the three site files into nginx and serve them (RK-0029, thepocketschool.mx's
# shape). Only index.html, style.css and images/ reach the web root. The
# Dockerfile, the manifest, the make files and CNAME never ship.
FROM nginx:stable-alpine

LABEL org.opencontainers.image.source="https://github.com/luisehk/herrada.me"
LABEL org.opencontainers.image.description="herrada.me static site"

# The stock web root holds nginx's own index.html and 50x.html. Empty it, so the
# image serves this site's files and nothing else.
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

COPY index.html style.css /usr/share/nginx/html/
COPY images/ /usr/share/nginx/html/images/

# 127.0.0.1 rather than `localhost`: nginx listens on IPv4 only and Alpine's
# busybox wget resolves `localhost` to ::1 first.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
