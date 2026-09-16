FROM caddy:2.10-alpine

COPY ./docker/caddy/Caddyfile.dev /etc/caddy/Caddyfile

EXPOSE 80

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
