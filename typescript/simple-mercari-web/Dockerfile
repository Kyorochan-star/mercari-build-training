# ビルドフェーズ
FROM node:20-alpine AS builder
WORKDIR /app

COPY . .

RUN npm install
RUN npm run build

# 実行フェーズ
FROM node:20-alpine
WORKDIR /app

RUN npm install -g serve

COPY --from=builder /app/dist /app/dist

EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]

