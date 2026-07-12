FROM node:20-alpine

WORKDIR /app

# Install dependencies for potential native modules
RUN apk add --no-cache curl git

# Copy package.json and install
COPY package.json package-lock.json* ./
RUN npm install --production

# Copy application
COPY . .

# Create data directory
RUN mkdir -p data/workspace data/exports data/builds

# Expose port
EXPOSE 4100

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:4100/status || exit 1

# Start server agent by default
CMD ["node", "server.js"]
