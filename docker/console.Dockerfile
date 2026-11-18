FROM node:22-alpine AS deps
WORKDIR /app
COPY console/package.json console/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY console/ ./
RUN npm run build

FROM node:22-alpine AS console
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
RUN mkdir -p public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
    CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["node", "server.js"]
