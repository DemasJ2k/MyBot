# Flowrex

Flowrex is a safety-first trading platform with:
- FastAPI backend (auth, data, strategies, backtesting, risk, execution)
- Next.js frontend (dashboards and controls)
- Postgres + Redis via Docker Compose

## Getting Started (Dev)

1. Copy environment variables:
   - `cp .env.example .env`
   - Fill in `APP_SECRET_KEY`, `JWT_SECRET_KEY`, and `TWELVEDATA_API_KEY`

2. Start services:
   - `docker-compose up -d`

3. Check health:
   - Backend: `http://localhost:8000/health`
   - Frontend: `http://localhost:3000`

## Prompt Sequence

Implementation follows the ordered prompts in `.github/prompts` (00 → 18).
