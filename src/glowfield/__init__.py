import argparse
import os


def main() -> None:
    import uvicorn

    env = os.environ.get
    parser = argparse.ArgumentParser(description="Run the Glowfield game server.")
    parser.add_argument("--host", default=env("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("PORT", "8000")))
    parser.add_argument(
        "--root-path",
        default=env("ROOT_PATH", ""),
        help="URL prefix when served from a subdirectory, e.g. /glowfield",
    )
    parser.add_argument(
        "--workers", type=int, default=int(env("WEB_CONCURRENCY", "1"))
    )
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    root_path = args.root_path.rstrip("/")
    print(f"Glowfield running at http://{args.host}:{args.port}{root_path}/", flush=True)
    uvicorn.run(
        "glowfield.app:app",
        host=args.host,
        port=args.port,
        root_path=root_path,
        workers=None if args.reload else args.workers,
        reload=args.reload,
        proxy_headers=True,
        forwarded_allow_ips=env("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
