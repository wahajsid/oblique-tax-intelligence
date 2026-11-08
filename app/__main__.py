"""Start the server: `python -m app`.

Reads PORT (default 8000) and HOST from the environment itself, so platform start
commands never depend on shell variable expansion (Railway, for example, ran the
Procfile command without a shell and passed the literal text "${PORT:-8000}").
"""
import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, proxy_headers=True, forwarded_allow_ips="*",
                log_level=os.environ.get("LOG_LEVEL", "info"))


if __name__ == "__main__":
    main()
