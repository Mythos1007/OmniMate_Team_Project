from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("ASSISTANT_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("ASSISTANT_WEB_PORT", "8090"))
    certfile = os.getenv("ASSISTANT_WEB_TLS_CERT", "").strip() or None
    keyfile = os.getenv("ASSISTANT_WEB_TLS_KEY", "").strip() or None

    kwargs = {
        "app": "app.main:app",
        "host": host,
        "port": port,
        "reload": False,
    }

    if certfile and keyfile:
        kwargs["ssl_certfile"] = certfile
        kwargs["ssl_keyfile"] = keyfile

    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()
