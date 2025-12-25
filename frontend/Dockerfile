# Multi-stage build for production
# Prompt 18 - Production Deployment

# ============================================================================
# Dependencies Stage
# ============================================================================
FROM node:20-alpine AS deps

# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# ============================================================================
# Build Stage
# ============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set build-time environment variables
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Build application
RUN npm run build

# ============================================================================
# Production Stage
# ============================================================================
FROM node:20-alpine AS runner

LABEL maintainer="Flowrex Team"
LABEL description="Flowrex Frontend Server"
LABEL version="1.0.0"

WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init curl

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 flowrex

# Set environment variables
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Copy built application
COPY --from=builder /app/public ./public

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=flowrex:nodejs /app/.next/standalone ./
COPY --from=builder --chown=flowrex:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER flowrex

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Run application with dumb-init
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
