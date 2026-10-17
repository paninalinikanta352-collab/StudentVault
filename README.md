# StudyVault API - Solo Backend Project

Student notes sharing API with JWT login, search, upvotes. No frontend needed - Swagger UI is the demo.

## Features
- Register / Login with hashed passwords (PBKDF2) + JWT (24h)
- Notes CRUD: subject, title, content, tags
- Search `?q=` + filter `?subject=` - ordered by upvotes
- Upvote (1 per user), owner-only delete
- Stats: total notes, upvotes, by-subject
- Seeded demo data + demo user

## Run
```powershell
cd StudyVault-API-Solo
C:\Python314\python.exe -m pip install -r requirements.txt
C:\Python314\python.exe -m uvicorn main:app --reload --port 8001
```
Open: http://127.0.0.1:8001/docs

Demo: `admin@studyvault.test` / `admin123`

## API
- `GET /api/health`
- `POST /api/auth/register` | `POST /api/auth/login`
- `GET /api/notes?q=&subject=` | `POST /api/notes` (auth)
- `POST /api/notes/{id}/upvote` (auth)
- `DELETE /api/notes/{id}` (owner only)
- `GET /api/stats`

## How auth works
1. Register -> password hashed with email as salt, stored
2. Login -> password checked -> server makes JWT `header.payload.signature`
3. Client sends `Authorization: Bearer <token>`
4. Server verifies signature + expiry, loads user

Built solo by Backend Lead.
Nalinikanta Pani 
