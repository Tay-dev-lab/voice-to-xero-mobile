"""
Render HTML for workflow interfaces.
"""

from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .base_session import BaseWorkflowSession


class HTMLRenderer:
    """Render HTML for workflow interfaces."""

    def __init__(self, templates_dir: str = "app/templates"):
        self.templates = Jinja2Templates(directory=templates_dir)

    def render_workflow_page(self, request: Request, workflow_name: str) -> str:
        """Render main workflow page."""
        return self.templates.TemplateResponse(
            f"{workflow_name}/index.html", {"request": request, "workflow": workflow_name}
        )

    def render_step_interface(
        self, step: str, session: BaseWorkflowSession, context: dict[str, Any] | None = None
    ) -> str:
        """Render interface for a workflow step."""
        base_context = {
            "current_step": step,
            "step_number": session.get_workflow_steps().index(step) + 1,
            "total_steps": len(session.get_workflow_steps()),
            "progress": session.get_progress_percentage(),
            "can_go_back": session.get_workflow_steps().index(step) > 0,
        }

        if context:
            base_context.update(context)

        return self.templates.get_template("partials/workflow/step_prompt.html").render(
            base_context
        )

    def render_step_result(
        self, step: str, data: dict[str, Any], session: BaseWorkflowSession
    ) -> str:
        """Render result display for completed step."""
        context = {
            "step": step,
            "data": data,
            "can_edit": step in session.completed_steps,
        }

        return self.templates.get_template("partials/workflow/step_result.html").render(context)

    def render_error(
        self, message: str, details: str | None = None, retry_action: str | None = None
    ) -> str:
        """Render error message."""
        return self.templates.get_template("partials/workflow/error_message.html").render(
            {
                "message": message,
                "details": details,
                "retry_action": retry_action,
            }
        )

    def render_success(
        self, message: str, next_action: str | None = None, next_label: str | None = None
    ) -> str:
        """Render success message."""
        return self.templates.get_template("partials/workflow/success_message.html").render(
            {
                "message": message,
                "next_action": next_action,
                "next_label": next_label,
            }
        )
