# Auth & User Management — Design (v1)

> Real authentication + admin user management for MRI-ReportGenerator. Replaces the
> mock JSON-cookie session. Decided with Andrew 2026-06-08; researched against OWASP
> (Password Storage + JWT cheat sheets) and current BFF practice.

## Architecture — BFF cookie + EEP-enforced JWT

```
browser ──(httpOnly cookie: JWT)──▶ Next.js (BFF) ──(Authorization: Bearer JWT)──▶ EEP ──validates──▶ /cases…
```

- **EEP issues and enforces** the JWT (Andrew's decision). The Next.js app is the front
  door: it holds the token in an httpOnly cookie and forwards it as a Bearer header on
  every server-side EEP call. Token never reaches browser JS (XSS-safe); works
  cross-origin locally (`:3000`↔`:8080`) without `SameSite=None`.
- **Login:** browser → Next.js server action → `EEP POST /auth/login` → verify (SQLite +
  Argon2id) → signed JWT → Next.js sets httpOnly cookie → redirect.
- **Per request:** Next.js client reads cookie server-side → `Authorization: Bearer` → EEP
  `current_user` dependency validates.
- **Logout:** Next.js clears the cookie (JWT is short-lived; see revocation).

## Security decisions (OWASP-aligned, 2026)

- **Password hashing: Argon2id** (`argon2-cffi`), OWASP params m=19 MiB, t=2, p=1, per-user
  salt managed by the lib. Fallback: stdlib `hashlib.scrypt` (N=2¹⁷, r=8, p=1) if the wheel
  is unavailable. Never store/log plaintext.
- **JWT: HS256**, signed with `JWT_SECRET` (env, never committed). Single issuer+validator
  (the EEP), so symmetric is appropriate; RS256/ES256 is the upgrade if more services
  validate. **Algorithm is pinned** on decode (`algorithms=["HS256"]`) — rejects `alg:none`
  and alg-confusion. Claims: `sub` (user id), `role`, `iat`, `exp`.
- **Token lifetime:** session token, env-configurable (`JWT_TTL_HOURS`, default 8 = a work
  shift). No refresh token in v1 (re-login on expiry) — acceptable for an internal clinical
  tool; **refresh-token rotation is the documented production upgrade**.
- **Revocation (better than pure-stateless):** `current_user` re-loads the user from SQLite
  by `sub` and checks `active` on every request. Deactivating/deleting a user blocks their
  token immediately, and role is always read fresh from the DB (token role is advisory).
- **Cookie:** httpOnly, `SameSite=Lax`, `Secure` in production only (local dev is http).
- **CSRF:** state-changing actions go through Next.js server actions (built-in Origin/Host
  checks) + `SameSite=Lax`. Explicit CSRF token = documented future hardening.
- **Authorization:** admin endpoints guarded by a server-side `require_admin` dependency at
  the EEP — not just hidden UI.
- **Secrets/data:** `JWT_SECRET`, `ADMIN_PASSWORD` via env; `users.db` gitignored.

## User store (SQLite, EEP)

`users` table: `id` (uuid), `email` (unique), `name`, `role`
(`admin|radiologist|technologist|viewer`), `password_hash`, `active` (bool),
`created_at`. Auto-created on boot; **seed admin** from `ADMIN_EMAIL`/`ADMIN_PASSWORD`
if the table is empty. DB path via `USERS_DB_PATH` (default `./data/users.db`, gitignored).

## API (EEP, new `services/eep/auth/` package)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | public | email+password → set-token (returns JWT) |
| GET  | `/auth/me` | user | current user from token |
| POST | `/auth/logout` | user | stateless ack (cookie cleared by BFF) |
| GET  | `/auth/users` | admin | list users |
| POST | `/auth/users` | admin | create user |
| PATCH| `/auth/users/{id}` | admin | change role / active |
| POST | `/auth/users/{id}/password` | admin | reset password |
| DELETE | `/auth/users/{id}` | admin | delete user |

`/cases*` become protected (any valid user). `/healthz`, `/readyz`, `/metrics`,
`/auth/login` stay open.

## Collision-safe file plan (§5)

- **New files (no collision):** `services/eep/auth/{__init__,security,db,deps,router}.py`
  + tests; all `frontend/` changes.
- **Shared-file touches (infra chat flagged):** `services/eep/app.py` (mount auth router +
  guard `/cases`) and `services/eep/requirements.txt` (+`pyjwt`, `argon2-cffi`). `config.py`
  untouched — auth reads env directly.

## Testing

- EEP `pytest`: Argon2 hash/verify; JWT encode/decode/expiry/alg-pinning; login
  success/fail; admin CRUD; role enforcement (401/403); deactivated-user rejection.
- Frontend (Playwright): login → worklist; admin creates a user → log out → that user logs
  in. 0 console errors.

## Out of scope (v1) — for later brainstorm

Refresh tokens, password self-service / change-password, email verification, account
lockout/rate-limit on login, audit log, SSO/OAuth.
