# =============================================================================
# DevSphere ERP — Frontend Dockerfile
#
# Stages:
#   development  — Next.js dev server with hot reload (default)
#   builder      — production build (npm run build)
#   production   — minimal image serving the pre-built Next.js output
# =============================================================================

# ---------------------------------------------------------------------------
# Stage: development — hot-reload dev server
# ---------------------------------------------------------------------------
FROM node:22-alpine AS development

ENV NODE_ENV=development

WORKDIR /app

# Copy package manifests first for layer-cache efficiency
COPY package.json package-lock.json* ./

RUN npm install

# Copy source (overridden by volume mount in docker-compose.yml)
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]

# ---------------------------------------------------------------------------
# Stage: builder — production build
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder

ENV NODE_ENV=production

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production --ignore-scripts

COPY . .

RUN npm run build

# ---------------------------------------------------------------------------
# Stage: production — standalone Next.js output
# ---------------------------------------------------------------------------
FROM node:22-alpine AS production

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --gid 1001 nodejs && \
    adduser --uid 1001 --ingroup nodejs --shell /bin/sh --disabled-password nextjs

WORKDIR /app

# Copy only the standalone output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
