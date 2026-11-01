# Telas do FarmáciaFácil prontas, servidas pelo Caddy (HTTPS na rede da farmácia).
FROM node:22-alpine AS telas
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2.8.4-alpine
COPY --from=telas /app/dist /srv
