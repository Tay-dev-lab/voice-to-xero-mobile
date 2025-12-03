"""
Contact workflow routes aggregator.
Combines all route modules into a single router.
"""

from fastapi import APIRouter

from .step_routes import router as step_router
from .submission_routes import router as submission_router
from .workflow_routes import router as workflow_router

# Create main router with prefix
router = APIRouter(prefix="/contact", tags=["contact-workflow"])

# Include all sub-routers
# IMPORTANT: step_router first - it has mobile JSON support for duplicate endpoints
router.include_router(step_router)
router.include_router(workflow_router)
router.include_router(submission_router)
