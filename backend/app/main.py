from fastapi import FastAPI

from .database import Base, engine
from .routers import auth, git, repos

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Stud Remote Server", version="1.0.0")

app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(git.router)


@app.get("/")
def root():
    return {"name": "stud-remote-server", "status": "ok"}
