"""
FastAPI application entry point for Voice to Xero authentication.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import Settings
from app.api.common import MobileAuthManager
from app.api.common.utils import get_session_or_ip
from app.api.session import SecureSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Initialize settings
settings = Settings()

# Initialize rate limiter
# Use session ID for rate limiting when available, otherwise use IP
limiter = Limiter(key_func=get_session_or_ip)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Debug mode: {settings.debug}")

    yield

    # Shutdown
    logger.info("Shutting down application")


def configure_middleware(app: FastAPI, settings: Settings) -> None:
    """
    Configure all middleware components for the application.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    # Add rate limiter to app state
    app.state.limiter = limiter

    # Add rate limit exceeded handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add request size limit middleware (15MB max)
    MAX_REQUEST_SIZE = 15 * 1024 * 1024

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        """Limit request size to prevent DoS attacks."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413, content={"detail": "Request too large. Maximum size is 15MB."}
            )
        return await call_next(request)

    # Add session middleware
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)


def configure_cors(app: FastAPI, settings: Settings) -> None:
    """
    Configure CORS settings for development.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    if settings.debug:
        cors_origins = settings.cors_origins.split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )


def configure_routes(app: FastAPI) -> None:
    """
    Register all API routes and endpoints.

    Args:
        app: FastAPI application instance
    """

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "healthy", "app": settings.app_name, "version": "0.1.0"}

    # Import and include routers
    from app.api.contact_workflow.routes import router as contact_router
    from app.api.invoice_workflow.routes import router as invoice_router
    from app.api.routes import router as auth_router

    app.include_router(auth_router)
    app.include_router(contact_router)
    app.include_router(invoice_router)


def initialize_services(app: FastAPI, settings: Settings) -> None:
    """
    Initialize application services and state.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    # Store session manager in app state for access in routes
    app.state.session_manager = SecureSessionManager(settings.session_secret_key)
    # Store mobile auth manager for JWT-based mobile authentication
    app.state.mobile_auth = MobileAuthManager(settings.session_secret_key)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.app_name,
        description="Voice-to-Xero authentication and invoice creation tool for tradesmen",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Configure application components
    configure_middleware(app, settings)
    configure_cors(app, settings)
    configure_routes(app)
    initialize_services(app, settings)

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=7001,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )
