FROM node:24-alpine AS builder

WORKDIR /workspace
RUN corepack enable
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json frontend/package.json
RUN pnpm install --frozen-lockfile --filter frontend

COPY frontend frontend
RUN pnpm --filter frontend build

FROM node:24-alpine AS app

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
COPY --from=builder /workspace/frontend/.next/standalone ./
COPY --from=builder /workspace/frontend/.next/static ./.next/static
COPY --from=builder /workspace/frontend/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
