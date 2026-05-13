# Backend Structure

Current backend is organized by responsibility:

- `app.py`: application entry point and runtime orchestration
- `api/`: HTTP routes and socket event registration
- `core/`: shared runtime primitives (metrics, future shared state/config helpers)
- `alerts.py`, `camera.py`, `chatbot.py`, `detector.py`, `face_recognition.py`, `prediction.py`, `reports.py`: domain services
- `missing_persons/`: persisted missing-person image assets

Compatibility wrappers:

- `routes.py` and `sockets.py` re-export `api` modules so older imports keep working.

