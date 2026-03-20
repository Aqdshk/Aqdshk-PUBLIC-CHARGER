FROM ghcr.io/cirruslabs/flutter:stable AS build

WORKDIR /app

# Build args for API and Chatbot URLs (set in docker-compose)
ARG API_BASE_URL=
ARG BOT_BASE_URL=

COPY pubspec.yaml ./
COPY pubspec.lock* ./
RUN flutter pub get

COPY . .
# Pass URLs to Flutter build (API + Chatbot) — set in .env / docker-compose build args
RUN BUILD_ARGS=""; \
    if [ -n "$API_BASE_URL" ]; then BUILD_ARGS="$BUILD_ARGS --dart-define=API_BASE_URL=$API_BASE_URL"; fi; \
    if [ -n "$BOT_BASE_URL" ]; then BUILD_ARGS="$BUILD_ARGS --dart-define=BOT_BASE_URL=$BOT_BASE_URL"; fi; \
    flutter build web --release $BUILD_ARGS

FROM nginx:alpine

COPY --from=build /app/build/web /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
