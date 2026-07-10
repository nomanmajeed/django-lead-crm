"""
Settings package entrypoint.

Default: local development settings.
Production: set ``DJANGO_ENV=prod`` in the environment or project-root ``.env``
(or point ``DJANGO_SETTINGS_MODULE`` at ``djcrm.settings.prod``).
"""

import os
from pathlib import Path

import environ

# Load .env before choosing local vs prod so DJANGO_ENV in .env is respected.
_base_dir = Path(__file__).resolve().parent.parent.parent
_env_file = _base_dir / ".env"
if _env_file.exists() and os.environ.get("READ_DOT_ENV_FILE", "true").lower() in {
    "1",
    "true",
    "yes",
}:
    environ.Env.read_env(_env_file)

_env = os.environ.get("DJANGO_ENV", "local").lower()

if _env in {"prod", "production"}:
    from .prod import *  # noqa: F403
else:
    from .local import *  # noqa: F403
