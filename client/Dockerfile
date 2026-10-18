FROM node:22-alpine AS build
WORKDIR /app
COPY certs/ /tmp/local-certs/
COPY package*.json ./
RUN touch /tmp/extra-ca.pem \
    && for cert in /tmp/local-certs/*.crt; do if [ -f "$cert" ]; then cat "$cert" >> /tmp/extra-ca.pem; printf '\n' >> /tmp/extra-ca.pem; fi; done \
    && if [ -s /tmp/extra-ca.pem ]; then NODE_EXTRA_CA_CERTS=/tmp/extra-ca.pem npm ci; else npm ci; fi
COPY . .
RUN npm run build
FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
