# Build an image capable of running the MCP HTTP server and Python crawler
FROM node:20-bookworm

# Install system dependencies for Python crawler
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests first for better caching
COPY requirements.txt ./
COPY mcp-server/package.json mcp-server/package.json
COPY mcp-server/package-lock.json mcp-server/package-lock.json

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Node dependencies in production mode
RUN npm ci --omit=dev --prefix mcp-server

# Copy the rest of the repository
COPY . .

ENV NODE_ENV=production \
    PORT=8000 \
    CRAWLER_PYTHON_BIN=python3

EXPOSE 8000

CMD ["npm", "start", "--prefix", "mcp-server"]
