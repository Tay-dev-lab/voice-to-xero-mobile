# Workflow Base Framework

## Overview
Reusable framework for creating multi-step voice-guided workflows.

## Usage Example

### 1. Create Your Session Class
```python
from app.api.workflow_base import BaseWorkflowSession

class InvoiceWorkflowSession(BaseWorkflowSession):
    def get_workflow_steps(self):
        return ["customer", "items", "payment", "review", "send"]
    
    def get_initial_step(self):
        return "customer"
    
    def validate_step_data(self, step, data):
        if step == "customer":
            return "customer_id" in data
        elif step == "items":
            return "line_items" in data and len(data["line_items"]) > 0
        return True
```

### 2. Create Your Router
```python
from app.api.workflow_base import BaseWorkflowRouter, HTMLRenderer

class InvoiceWorkflowRouter(BaseWorkflowRouter):
    def __init__(self):
        super().__init__(
            prefix="/invoice-workflow",
            workflow_name="invoice",
            session_class=InvoiceWorkflowSession,
            renderer=HTMLRenderer()
        )
    
    def register_workflow_routes(self):
        # Add invoice-specific routes
        @self.router.post("/add-line-item")
        async def add_line_item(request: Request):
            # Custom logic here
            pass
    
    def process_step_data(self, step, data, session):
        # Process and validate step data
        if step == "items":
            # Parse line items
            return {"line_items": parse_items(data)}
        return data
```

### 3. Register in Main App
```python
from app.api.invoice_workflow.router import InvoiceWorkflowRouter

invoice_router = InvoiceWorkflowRouter()
app.include_router(invoice_router.router)
```

## Components

### BaseWorkflowSession
- Manages workflow state and progression
- Tracks completed steps and data
- Provides navigation between steps

### BaseWorkflowRouter
- Handles common HTTP endpoints
- Manages session lifecycle
- Provides extension points for customization

### VoiceStepProcessor
- Transcribes audio using OpenAI Whisper
- Parses transcripts with GPT structured output
- Validates and sanitizes data

### HTMLRenderer
- Renders Jinja2 templates
- Provides consistent UI components
- Handles error and success states

## Reusability

This framework provides 70% of common workflow functionality:
- Session management
- Step navigation
- Voice processing
- HTML rendering
- Error handling

You only need to implement:
- Workflow-specific steps
- Custom validation logic
- Specialized data processing