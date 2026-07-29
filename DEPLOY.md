# SmartVideo Platform Deployment Guide

## Prerequisites

- **Python** >= 3.11 (recommended: 3.12)
- **Node.js** >= 20 (for frontend development)
- **pnpm** >= 8 (for frontend build)
- **FFmpeg** (for video stitching, optional in placeholder mode)
- **OpenAI API Key** (for LLM/video generation)

## Option 1: Docker Deployment (Recommended)

### 1. Set up environment

\\\ash
# Copy environment template and edit
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys
# At minimum: OPENAI_API_KEY=
\\\

### 2. Build and start

\\\ash
# Build all services
docker-compose build

# Start in background
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop
docker-compose down
\\\

### 3. Verify

\\\ash
# Health check
curl http://localhost:8765/api/v1/health
# -> {"status":"ok","version":"0.2.0"}

# Frontend
open http://localhost
\\\

## Option 2: Local Development

### Backend

\\\ash
cd backend

# Create virtual environment
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -e ".[all]"

# Copy environment file
copy .env.example .env
# Edit .env with your API keys

# Start API server
uvicorn app.main:app --reload --port 8765

# Run tests
pytest
\\\

### Frontend

\\\ash
cd frontend

# Install dependencies
pnpm install

# Start dev server (proxies API to localhost:8765)
pnpm dev

# Build for production
pnpm run build
\\\

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | \/api/v1/health\ | Health check |
| GET | \/api/v1/projects/\ | List projects |
| POST | \/api/v1/projects/\ | Create project |
| GET | \/api/v1/projects/{id}\ | Get project |
| PATCH | \/api/v1/projects/{id}\ | Update project |
| DELETE | \/api/v1/projects/{id}\ | Delete project |
| POST | \/api/v1/workspace/run/{id}\ | Run pipeline |
| GET | \/api/v1/reviews/\ | List reviews |
| POST | \/api/v1/reviews/{id}/approve\ | Approve review |
| POST | \/api/v1/reviews/{id}/reject\ | Reject review |
| GET | \/api/v1/assets/\ | List assets |
| GET | \/api/v1/assets/search?q=\ | Search assets |
| POST | \/api/v1/publish/{id}\ | Publish video |
| WS | \/api/v1/ws/{project_id}\ | WebSocket |

## CLI Usage

\\\ash
# Run pipeline from CLI
smartvideo run "30 second product ad" --name "My Project"

# List projects
smartvideo project list

# Get project details
smartvideo project get <project_id>
\\\

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| \OPENAI_API_KEY\ | - | OpenAI API key |
| \OPENAI_BASE_URL\ | - | OpenAI-compatible API endpoint |
| \OPENAI_MODEL\ | gpt-4o-mini | LLM model |
| \VIDEO_PROVIDER\ | placeholder | Video provider (placeholder/openai_videos/http) |
| \VIDEO_API_BASE_URL\ | - | Video generation API endpoint |
| \AUDIO_ENABLE\ | 1 | Enable audio processing |

## Production Checklist

- [ ] Set \OPENAI_API_KEY\ in \.env\
- [ ] Set \VIDEO_PROVIDER\ to real provider (not placeholder)
- [ ] Configure \FFmpeg\ in PATH
- [ ] Change CORS origins from \*\ to specific domain
- [ ] Set up proper SQL database (MySQL/PostgreSQL)
- [ ] Configure monitoring (Langfuse/LangSmith)
- [ ] Set up reverse proxy (Nginx) with HTTPS
- [ ] Enable authentication/RBAC
