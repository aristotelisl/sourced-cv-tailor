import logging

from fastapi import FastAPI

from backend.api import analyse, applications, extras, profile, render, tailor

# Show the per-call cost lines from backend.llm.usage in the backend's console window.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:     %(message)s")
logging.getLogger("cv_tailor").setLevel(logging.INFO)

app = FastAPI(title="CV Tailor")
app.include_router(profile.router)
app.include_router(analyse.router)
app.include_router(tailor.router)
app.include_router(render.router)
app.include_router(applications.router)
app.include_router(extras.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
