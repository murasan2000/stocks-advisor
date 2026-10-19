# ---- deps ----
FROM node:22-slim AS deps

WORKDIR /web

COPY package.json package-lock.json ./
RUN npm ci

# ---- dev ----
# docker compose（ローカル開発）用。ソースはバインドマウントし、node_modules は
# このイメージ内（Linux 向けネイティブバイナリ）のものを使う。
FROM deps AS dev

EXPOSE 5173

CMD ["npm", "run", "dev"]

# ---- build ----
FROM deps AS build

COPY . .
RUN npm run build

# ---- serve ----
FROM nginx:1.27-alpine AS serve

COPY --from=build /web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
