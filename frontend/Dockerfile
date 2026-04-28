# Stage 1: Build the React/Vite SPA
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
# npm install instead of npm ci so no lock file is required at first build.
# Commit the generated package-lock.json and switch to `npm ci` for
# fully reproducible subsequent builds.
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve with Caddy
# The compiled dist/ is baked into the image at /srv.
# The Caddyfile is bind-mounted at runtime from ./caddy/Caddyfile so TLS
# cert data stays on the host (caddy_data volume).
FROM caddy:2-alpine

COPY --from=build /app/dist /srv

EXPOSE 80 443
