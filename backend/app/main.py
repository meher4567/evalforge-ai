from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="EvalForge AI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    return app


app = create_app()
