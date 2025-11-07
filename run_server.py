#!/usr/bin/env python3
import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Extraction API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    print(f"Starting server on http://{args.host}:{args.port}")
    print(f"Docs: http://{args.host}:{args.port}/docs")
    print(f"Auto-reload: {'enabled' if args.reload else 'disabled'}\n")

    uvicorn.run(
        "app.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
