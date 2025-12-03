"""
Unit tests for BaseWorkflowSession.
"""

from app.api.workflow_base.base_session import BaseWorkflowSession


class TestWorkflowSession(BaseWorkflowSession):
    """Test implementation of BaseWorkflowSession."""

    def get_workflow_steps(self):
        return ["step1", "step2", "step3", "complete"]

    def get_initial_step(self):
        return "step1"

    def validate_step_data(self, step, data):
        # Simple validation for testing
        return step in data


def test_session_initialization():
    """Test session creates with correct defaults."""
    session = TestWorkflowSession()

    assert session.session_id is not None
    assert session.current_step == "step1"
    assert session.completed_steps == []
    assert session.workflow_data == {}


def test_advance_step():
    """Test advancing through workflow steps."""
    session = TestWorkflowSession()

    # Mark first step complete
    session.mark_step_complete("step1", {"step1": "data"})

    # Advance to next step
    next_step = session.advance_step()
    assert next_step == "step2"
    assert session.current_step == "step2"


def test_go_to_step():
    """Test navigation to specific steps."""
    session = TestWorkflowSession()

    # Complete first two steps
    session.mark_step_complete("step1", {"step1": "data"})
    session.advance_step()
    session.mark_step_complete("step2", {"step2": "data"})

    # Should be able to go back to step1
    assert session.go_to_step("step1") is True
    assert session.current_step == "step1"

    # Should not be able to skip to complete
    assert session.go_to_step("complete") is False


def test_progress_calculation():
    """Test progress percentage calculation."""
    session = TestWorkflowSession()

    assert session.get_progress_percentage() == 0.0

    session.mark_step_complete("step1", {})
    assert session.get_progress_percentage() == 25.0

    session.mark_step_complete("step2", {})
    assert session.get_progress_percentage() == 50.0
