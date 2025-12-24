# Prompt 01: Project Scaffold

## Objective
Create the complete project structure, Docker environment, and foundational configuration for Flowrex.

## Deliverables
- Backend and frontend directory structures
- Docker Compose configuration
- Environment variable setup
- Basic application entry points
- All services running successfully

---

## Step 1: Create Root Directory Structure

Create the following structure:
```
flowrex/
├── backend/
├── frontend/
├── nginx/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.dev.yml
└── README.md
```

---

## Step 2: Backend Structure

Create backend directory with Python project structure:
```bash
mkdir -p backend/app/{api/v1,models,schemas,auth,core,services}
mkdir -p backend/tests/{unit,integration,e2e}
mkdir -p backend/alembic/versions
```

Create `backend/requirements.txt`:
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
asyncpg==0.29.0
redis==5.0.1
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.2
slowapi==0.1.9
httpx==0.26.0
aiohttp==3.9.1
websockets==12.0
numpy==1.26.3
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
python-dotenv==1.0.0
```

Create `backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Flowrex Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

@app.get("/")
async def root():
    return {"message": "Flowrex API", "docs": "/docs"}
```

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## Step 3: Frontend Structure

Create frontend with Next.js:
```bash
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
```

Update `frontend/package.json` to add:
```json
{
  "dependencies": {
    "axios": "^1.6.5",
    "zustand": "^4.5.0",
    "lightweight-charts": "^4.1.1",
    "lucide-react": "^0.312.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  }
}
```

Create `frontend/Dockerfile`:
```dockerfile
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM base AS builder
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

Update `frontend/next.config.js`:
```javascript
module.exports = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
    ]
  },
}
```

---

## Step 4: Docker Compose Configuration

Create `docker-compose.yml`:
```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    container_name: flowrex-postgres
    environment:
      POSTGRES_USER: flowrex
      POSTGRES_PASSWORD: flowrex_dev_pass
      POSTGRES_DB: flowrex
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U flowrex"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: flowrex-redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: flowrex-backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://flowrex:flowrex_dev_pass@postgres:5432/flowrex
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: flowrex-frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - NEXT_PUBLIC_API_BASE=/api/v1

volumes:
  postgres_data:
  redis_data:
```

---

## Step 5: Environment Configuration

Create `.env.example`:
```bash
# Database
POSTGRES_USER=flowrex
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=flowrex
DATABASE_URL=postgresql+asyncpg://flowrex:password@localhost:5432/flowrex

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
APP_SECRET_KEY=generate_with_openssl_rand_hex_32
JWT_SECRET_KEY=generate_with_openssl_rand_hex_32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# TwelveData API
TWELVEDATA_API_KEY=your_api_key_here

# Frontend
NEXT_PUBLIC_API_BASE=/api/v1
```

---

## Step 6: Initialize Git Repository

Create `.gitignore`:
```
__pycache__/
*.py[cod]
*$py.class
.env
.venv
venv/
.pytest_cache/
.coverage
htmlcov/
*.log
.DS_Store
node_modules/
.next/
dist/
build/
*.local
postgres_data/
redis_data/
```

Initialize git:
```bash
git init
git add .
git commit -m "feat: Initial project scaffold"
```

---

## Step 7: Start and Validate Services

Start all services:
```bash
docker-compose up -d
```

Verify each service:
```bash
# Check all services running
docker-compose ps

# Test PostgreSQL
docker-compose exec postgres psql -U flowrex -c "SELECT 1"

# Test Redis
docker-compose exec redis redis-cli ping

# Test backend
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000
```

---

## Validation Checklist
- [ ] All directories created
- [ ] requirements.txt has all dependencies
- [ ] package.json has all dependencies
- [ ] Dockerfiles created for backend and frontend
- [ ] docker-compose.yml configured
- [ ] .env.example created
- [ ] .gitignore created
- [ ] docker-compose up -d runs without errors
- [ ] PostgreSQL accepts connections
- [ ] Redis responds to PING
- [ ] Backend /health returns 200
- [ ] Frontend loads on localhost:3000
- [ ] No errors in docker logs

---

## Completion Criteria
1. Run `docker-compose ps` - all services show "healthy" or "running"
2. Run `curl http://localhost:8000/health` - returns JSON
3. Open browser to http://localhost:3000 - page loads
4. Check logs: `docker-compose logs backend` - no errors
5. Check logs: `docker-compose logs frontend` - no errors

When all criteria met, proceed to Prompt 02.
