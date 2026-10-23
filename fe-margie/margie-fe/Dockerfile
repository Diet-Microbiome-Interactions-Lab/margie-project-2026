# MARGIE's website: the interface as static files, cluster only, served by nginx.
# Build:  docker build -t <registry>/margie-web:<version> .
# The API's address is same-origin: the ingress sends /v1 to the API and the rest here.
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV VITE_PUBLIC_API_URL=""
RUN npm run build

FROM nginx:1.27-alpine
# Two workers: "auto" starts one per CPU of the host (over a hundred on a large host), which
# overruns the pod's memory limit.
RUN sed -i 's/^worker_processes[[:space:]]*auto;/worker_processes 2;/' /etc/nginx/nginx.conf \
    && grep -q '^worker_processes 2;' /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
