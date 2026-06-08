"""Authentication & user management for the EEP.

New, self-contained package (see docs/auth-design.md). Public auth API lives in
`router.py`; password hashing + JWT in `security.py`; the SQLite user store in
`db.py`; FastAPI guards in `deps.py`. The only edits outside this package are a
couple of wiring lines in the EEP `app.py` and two deps in `requirements.txt`.
"""
