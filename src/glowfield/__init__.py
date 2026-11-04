import argparse


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Glowfield game server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()
    print(f"Glowfield running at http://{args.host}:{args.port}")
    uvicorn.run("glowfield.app:app", host=args.host, port=args.port, reload=args.reload)
