# Next.js frontend — multi-stage, standalone output.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
# NEXT_PUBLIC_* are inlined at build time, so the API mode + EEP URL must be baked here.
# Default to mock so a plain `docker build` still produces a self-contained image; the AWS
# deploy passes --build-arg NEXT_PUBLIC_API_MODE=live + the EEP's public URL.
ARG NEXT_PUBLIC_API_MODE=mock
ARG NEXT_PUBLIC_EEP_URL=
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_MODE=$NEXT_PUBLIC_API_MODE \
    NEXT_PUBLIC_EEP_URL=$NEXT_PUBLIC_EEP_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# standalone server + static assets + public dir
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
