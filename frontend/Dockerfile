# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# npm 走 npmmirror.com（中国镜像）。决策室授权的 judgment call。
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com

# 先装依赖（利用 Docker 缓存）
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# 复制源码并 build
COPY tsconfig*.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public

RUN npm run build

# 服务阶段
FROM nginx:1.27-alpine

# 拷贝 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
