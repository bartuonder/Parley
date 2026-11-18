import argparse
import asyncio
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Parley ticket service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "parley.service.api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        loop="none" if sys.platform == "win32" else "auto",
    )


if __name__ == "__main__":
    main()
