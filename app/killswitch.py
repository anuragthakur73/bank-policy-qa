# Kill switch (ADR-013; RBI draft model-risk guidance: ability to stop the model). Env KILL_SWITCH=1, or a file named
# KILL_SWITCH in the working folder - the file works without a restart. Own module (Week 5 S3) so the API, the
# screen and the LangGraph answer flow all read the same switch without importing FastAPI.
import os, pathlib

def kill_switch_on() -> bool:
    return os.environ.get("KILL_SWITCH") == "1" or pathlib.Path("KILL_SWITCH").exists()
