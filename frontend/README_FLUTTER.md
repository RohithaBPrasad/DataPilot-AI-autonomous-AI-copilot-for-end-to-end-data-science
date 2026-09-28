# Atlas Flutter client

This directory is now the Flutter Web client for the Autonomous Data Scientist backend.

## Run locally

From `frontend/` with Flutter installed:

```powershell
flutter pub get
flutter run -d chrome --web-port 3000 --dart-define=API_BASE_URL=http://localhost:8000
```

Build a deployable browser bundle with:

```powershell
flutter build web --release --dart-define=API_BASE_URL=https://your-api.example.com
```

The client uses the existing FastAPI endpoints for conversation history, uploads, SSE chat, and report downloads. The sign-in surface is currently a local workspace gate; production identity should be connected to the backend before public deployment.
