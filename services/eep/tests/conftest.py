"""Hermetic test env — temp DBs + a test JWT secret, set BEFORE the app imports
(so neither the real users.db nor workflow.db is touched by the suite)."""

import os
import tempfile

_TMP = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_TMP, "users.db")
os.environ["WORKFLOW_DB_PATH"] = os.path.join(_TMP, "workflow.db")
os.environ["JWT_SECRET"] = "test-secret-min-32-bytes-long-aaaaaaaa"
os.environ["DEMO_PASSWORD"] = "demo12345"
