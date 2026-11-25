
# ==========================================
# STAGE 1 — BUILD REACT APPLICATION
# ==========================================

FROM node:24-alpine AS builder

WORKDIR /app

# Install dependencies using the lockfile
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source
COPY . .

# API URL used by the browser
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Generate optimized production assets
RUN npm run build


# ==========================================
# STAGE 2 — SERVE WITH NGINX
# ==========================================

FROM nginx:stable-alpine AS runtime

# Copy production assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
