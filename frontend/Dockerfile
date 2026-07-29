# Build stage
FROM node:24-alpine AS build
RUN npm install -g pnpm
WORKDIR /app
COPY package.json ./
RUN pnpm install
COPY . .
RUN pnpm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
