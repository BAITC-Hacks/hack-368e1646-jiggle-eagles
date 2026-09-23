# scripts/start-docker.sh supplies NODE_VERSION from .nvmrc.
ARG NODE_VERSION
FROM node:${NODE_VERSION}-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/
COPY backend/package.json ./backend/
RUN npm ci --include=dev --no-audit --no-fund
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./frontend/
COPY frontend/src ./frontend/src
COPY backend/tsconfig.json ./backend/
COPY backend/src ./backend/src
# Tests run outside the image; compile only application sources here.
RUN npm run typecheck --workspace frontend && npm run build --workspace frontend && npm run build --workspace backend

FROM node:${NODE_VERSION}-bookworm-slim AS production-dependencies
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/
COPY backend/package.json ./backend/
RUN npm ci --omit=dev --workspace backend --include-workspace-root --no-audit --no-fund && npm cache clean --force

FROM node:${NODE_VERSION}-bookworm-slim AS runtime
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=production-dependencies /app/node_modules ./node_modules
COPY --from=production-dependencies /app/package.json ./package.json
COPY --from=production-dependencies /app/backend/package.json ./backend/package.json
COPY --from=build /app/backend/dist ./backend/dist
COPY --from=build /app/frontend/dist ./frontend/dist
USER node
EXPOSE 3000
CMD ["node", "backend/dist/server.js"]
