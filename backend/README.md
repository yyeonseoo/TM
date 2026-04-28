## Backend (FastAPI)

### Run

```bash
cd backend
python -m pip install -r requirements.txt

# set env vars (zsh)
export NAVER_CLIENT_ID="..."
export NAVER_CLIENT_SECRET="..."

uvicorn backend.main:app --port 8000 --reload
```

### API

- `POST /api/runs`: create run + start collect job
- `GET /api/jobs/{jobId}`: job status/polling
- `GET /api/runs/{runId}/articles`: collected articles
- `POST /api/runs/{runId}/analyze`: start analyze job
- `GET /api/runs/{runId}/issues`: issues result

Data is stored under `backend/data/runs/{runId}/`.
