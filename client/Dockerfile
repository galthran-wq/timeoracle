FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build-only

FROM node:22-slim
WORKDIR /app
COPY --from=build /app/dist ./dist

CMD ["tail", "-f", "/dev/null"]
