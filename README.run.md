# Independent Case Pipeline Runbook

This file records the direct way to run the project without any one-click wrapper.

## What runs

- Backend API: Python HTTP service on `http://127.0.0.1:8000`
- Frontend: Vite dev server on `http://127.0.0.1:5173`

Open two terminals and keep both running while you use the app.

## 1. Prepare the backend environment

If the Conda environment does not exist yet, run:

```powershell
.\setup_env.ps1
```

This creates the backend environment at:

```text
.\.conda\case-pipeline
```

## 2. Start the backend

From the project root:

```powershell
& '.\.conda\case-pipeline\python.exe' '.\backend\app\main.py' --host 127.0.0.1 --port 8000
```

When it starts correctly, the backend serves:

- `GET /api/health`
- `GET /api/settings`
- `POST /api/extract`
- `POST /api/render`
- `GET /api/files?path=...`

Quick check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

## 3. Start the frontend

In a second terminal:

```powershell
Set-Location .\frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

If frontend dependencies are missing, install them first:

```powershell
Set-Location .\frontend
npm install
```

## 4. Open the app

After both services are running, open:

```text
http://127.0.0.1:5173
```

The frontend talks to the local backend on port `8000`.

## Notes

- Run the backend command from the project root.
- Run the frontend command from the `frontend` directory.
- If a generated Word file is open in Word or WPS, rendering may fail because the file is locked.
