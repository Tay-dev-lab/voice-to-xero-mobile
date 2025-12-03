"""
Abstract base class for workflow routers.
"""

from abc import ABC, abstractmethod
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .base_session import BaseWorkflowSession
from .html_renderer import HTMLRenderer


class BaseWorkflowRouter(ABC):
    """Abstract base class for workflow routers."""

    def __init__(
        self,
        prefix: str,
        workflow_name: str,
        session_class: type[BaseWorkflowSession],
        renderer: HTMLRenderer,
    ):
        self.router = APIRouter(prefix=prefix, tags=[workflow_name])
        self.workflow_name = workflow_name
        self.session_class = session_class
        self.renderer = renderer
        self.sessions: dict[str, BaseWorkflowSession] = {}

        # Register common routes
        self._register_common_routes()

        # Let subclass register specific routes
        self.register_workflow_routes()

    @abstractmethod
    def register_workflow_routes(self):
        """Register workflow-specific routes."""

    @abstractmethod
    def process_step_data(
        self, step: str, data: dict[str, Any], session: BaseWorkflowSession
    ) -> dict[str, Any]:
        """Process data for a specific step."""

    def _register_common_routes(self):
        """Register routes common to all workflows."""

        @self.router.get("/")
        async def get_workflow_page(request: Request):
            """Render the main workflow page."""
            return self.renderer.render_workflow_page(request, self.workflow_name)

        @self.router.post("/start")
        async def start_workflow(request: Request):
            """Initialize a new workflow session."""
            session = self.session_class()
            self.sessions[session.session_id] = session

            # Store session ID in HTTP session
            request.session["session_id"] = session.session_id

            return JSONResponse(
                {
                    "session_id": session.session_id,
                    "current_step": session.current_step,
                    "workflow": self.workflow_name,
                }
            )

        @self.router.get("/session/{session_id}")
        async def get_session_status(session_id: str):
            """Get current session status."""
            session = self._get_session(session_id)
            return JSONResponse(session.to_dict())

        @self.router.post("/step/{step}/navigate")
        async def navigate_to_step(step: str, request: Request):
            """Navigate to a specific step."""
            session_id = request.session.get("session_id")
            session = self._get_session(session_id)

            if session.go_to_step(step):
                return HTMLResponse(self.renderer.render_step_interface(step, session))
            else:
                raise HTTPException(status_code=400, detail=f"Cannot navigate to step: {step}")

        @self.router.post("/step/{step}/complete")
        async def complete_step(step: str, request: Request):
            """Mark a step as complete."""
            session_id = request.session.get("session_id")
            session = self._get_session(session_id)

            # Get and process step data
            form_data = await request.form()
            processed_data = self.process_step_data(step, dict(form_data), session)

            # Mark complete and advance
            session.mark_step_complete(step, processed_data)
            next_step = session.advance_step()

            return JSONResponse(
                {
                    "completed": True,
                    "next_step": next_step,
                    "progress": session.get_progress_percentage(),
                }
            )

    def _get_session(self, session_id: str | None) -> BaseWorkflowSession:
        """Retrieve session by ID or raise error."""
        if not session_id or session_id not in self.sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        return self.sessions[session_id]
