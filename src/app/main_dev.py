# Used for debugging - sets the event loop policy for Windows before uvicorn starts
# alternatively for Windows development consider running the app from a WSL shell

# This file should be ignored by docker and not included in production builds

import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    port = "--port" in sys.argv and int(sys.argv[sys.argv.index("--port") + 1]) or 8000
    reload = "--reload" in sys.argv

    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=reload)
