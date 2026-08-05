import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "resume_campaign_agent.api:app",
        host=os.getenv("AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENT_PORT", "18010")),
        reload=False,
    )
