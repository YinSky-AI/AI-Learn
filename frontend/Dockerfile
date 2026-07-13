# =============================================================================
# AI 智能学习平台 - Frontend Dockerfile
# Node 18-alpine 多阶段构建
# =============================================================================

# -- Stage 1: 安装依赖 --
FROM node:18-alpine AS deps

WORKDIR /app

# 先复制依赖描述文件，利用 Docker 缓存
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./

# 根据 lock 文件选择安装方式（优先 npm）
RUN if [ -f package-lock.json ]; then \
        npm ci --ignore-scripts; \
    elif [ -f yarn.lock ]; then \
        yarn install --frozen-lockfile; \
    elif [ -f pnpm-lock.yaml ]; then \
        corepack enable pnpm && pnpm install --frozen-lockfile; \
    else \
        npm install; \
    fi

# -- Stage 2: 构建阶段 --
FROM node:18-alpine AS builder

WORKDIR /app

# 从 deps 复制 node_modules
COPY --from=deps /app/node_modules ./node_modules

# 复制完整源码
COPY . .

# 设置构建时环境变量
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# 构建 Next.js 应用
RUN npm run build

# -- Stage 3: 运行阶段 --
FROM node:18-alpine AS runner

WORKDIR /app

# 设置环境变量
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 创建非 root 用户
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 复制产物
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./package.json
COPY --from=builder --chown=nextjs:nodejs /app/next.config.js ./

USER nextjs

EXPOSE 3000

# 启动 Next.js
CMD ["npm", "start"]
