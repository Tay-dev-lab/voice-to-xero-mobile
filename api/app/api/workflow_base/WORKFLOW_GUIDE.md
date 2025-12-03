# Workflow Framework Guide

## Overview

The Workflow Framework provides a reusable foundation for building multi-step voice-guided workflows. It was designed following KISS principles to minimize complexity while maximizing reusability.

## Architecture

```
workflow_base/              # Reusable framework (70% of functionality)
├── base_session.py        # Session state management
├── base_router.py         # Common HTTP endpoints
├── step_processor.py      # Voice processing pipeline
├── html_renderer.py       # Template rendering
├── config.py             # Configuration management
├── exceptions.py         # Error handling
├── cache.py             # Caching utilities
└── parsing_utils.py     # Common parsing functions

contact_workflow/          # Specific implementation (30% custom)
├── routes/               # HTTP endpoints
├── validators/           # Field & session validation
├── config.py            # Contact-specific config
├── session_store.py     # Extends base session
└── step_handlers.py     # Contact-specific parsing
```

## Creating a New Workflow

### Step 1: Define Your Configuration

Create a configuration class that extends `BaseWorkflowConfig`:

```python
# app/api/invoice_workflow/config.py
from app.api.workflow_base.config import BaseWorkflowConfig

class InvoiceWorkflowConfig(BaseWorkflowConfig):
    app_name = "Invoice Workflow"
    
    def get_workflow_steps(self) -> List[str]:
        return ["customer", "items", "payment_terms", "review", "send"]
    
    def get_step_prompts(self) -> Dict[str, str]:
        return {
            "customer": "Please say the customer's name or select from existing.",
            "items": "Describe the items or services for this invoice.",
            "payment_terms": "Specify payment terms (e.g., Net 30).",
            "review": "Review the invoice details.",
            "send": "Ready to send the invoice.",
        }
    
    def get_validation_rules(self) -> Dict[str, Any]:
        return {
            "customer": {"required": True},
            "items": {"min_items": 1, "max_items": 100},
            "amount": {"min": 0.01, "max": 1000000},
        }
```

### Step 2: Create Your Session Class

Extend `BaseWorkflowSession` with workflow-specific logic:

```python
# app/api/invoice_workflow/session_store.py
from app.api.workflow_base import BaseWorkflowSession

class InvoiceWorkflowSession(BaseWorkflowSession):
    def __init__(self, session_id: Optional[str] = None):
        super().__init__(session_id)
        self.invoice_data = {}
        self.line_items = []
    
    def get_workflow_steps(self) -> List[str]:
        config = get_invoice_config()
        return config.get_workflow_steps()
    
    def validate_step_data(self, step: str, data: Dict[str, Any]) -> bool:
        if step == "customer":
            return bool(data.get("customer_id") or data.get("customer_name"))
        elif step == "items":
            return len(self.line_items) > 0
        return True
    
    def add_line_item(self, item: Dict[str, Any]):
        self.line_items.append(item)
        self.mark_step_complete("items", {"items": self.line_items})
```

### Step 3: Implement Step Handlers

Create step-specific parsing logic:

```python
# app/api/invoice_workflow/step_handlers.py
from app.api.workflow_base import VoiceStepProcessor
from app.api.workflow_base.parsing_utils import clean_transcript

async def process_invoice_step(
    step: str,
    audio_file: UploadFile,
    openai_api_key: str
) -> Dict[str, Any]:
    processor = VoiceStepProcessor(openai_api_key)
    
    # Transcribe audio
    transcript = await processor.transcribe_audio(audio_file)
    transcript = clean_transcript(transcript)
    
    # Parse based on step
    if step == "customer":
        return await parse_customer(transcript, processor)
    elif step == "items":
        return await parse_line_items(transcript, processor)
    # ... other steps
```

### Step 4: Set Up Routes

Create route modules following the pattern:

```python
# app/api/invoice_workflow/routes/__init__.py
from fastapi import APIRouter
from .workflow_routes import router as workflow_router
from .item_routes import router as item_router
from .submission_routes import router as submission_router

router = APIRouter(prefix="/invoice", tags=["invoice-workflow"])
router.include_router(workflow_router)
router.include_router(item_router)
router.include_router(submission_router)
```

### Step 5: Register in Main App

Add your workflow to the main FastAPI app:

```python
# app/main.py
from app.api.invoice_workflow.routes import router as invoice_router

app.include_router(invoice_router)
```

## Best Practices

### 1. Keep Files Small
- No file should exceed 300 lines
- Split large modules into focused components
- Use the validators/ pattern for validation logic

### 2. Reuse Framework Components
- Use `VoiceStepProcessor` for all voice processing
- Extend `BaseWorkflowSession` for session management
- Use `parsing_utils` for common parsing patterns

### 3. Configuration-Driven Development
- Put all prompts in configuration
- Define validation rules in config
- Use config for rate limits

### 4. Error Handling
- Use custom exceptions from `workflow_base.exceptions`
- Provide user-friendly error messages
- Log technical details for debugging

### 5. Testing Strategy
```python
# tests/test_invoice_workflow.py
import pytest
from app.api.invoice_workflow.session_store import InvoiceWorkflowSession

def test_invoice_session_creation():
    session = InvoiceWorkflowSession()
    assert session.current_step == "customer"
    assert len(session.line_items) == 0

def test_add_line_item():
    session = InvoiceWorkflowSession()
    item = {"description": "Consulting", "amount": 1000}
    session.add_line_item(item)
    assert len(session.line_items) == 1
```

## Common Patterns

### Adding Custom Validation
```python
# In your validators module
def validate_invoice_amount(amount: float) -> bool:
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if amount > 1000000:
        raise ValueError("Amount exceeds maximum")
    return True
```

### Caching API Responses
```python
from app.api.workflow_base.cache import cache_api

@cache_api
async def get_customer_list(api_key: str) -> List[Dict]:
    # Expensive API call - will be cached for 5 minutes
    return await fetch_customers_from_api(api_key)
```

### Custom Step Navigation
```python
def can_skip_step(self, step: str) -> bool:
    # Allow skipping optional steps
    optional_steps = ["payment_terms", "notes"]
    return step in optional_steps
```

## Performance Tips

1. **Use Caching**: Cache expensive operations with `@cache_api`
2. **Batch Operations**: Process multiple items together
3. **Async Processing**: Use async/await for I/O operations
4. **Lazy Loading**: Only load data when needed

## Troubleshooting

### Session Not Found
- Check session expiry (default 30 minutes)
- Verify session_id format (UUID v4)
- Check session cleanup isn't too aggressive

### Voice Processing Fails
- Verify OpenAI API key is valid
- Check audio file format (webm, mp3, wav supported)
- Ensure file size < 10MB

### Validation Errors
- Check field validators in validators/ module
- Verify configuration rules match validation logic
- Test with known good data

## Migration Guide

### From Monolithic to Modular
1. Extract HTML to templates/
2. Split routes.py into route modules
3. Move validation to validators/
4. Extract configuration to config.py
5. Update imports throughout

### Adding New Features
1. Start with configuration
2. Extend session if needed
3. Add step handlers
4. Create routes
5. Write tests
6. Document changes

## API Reference

See individual module documentation:
- [Base Session](./base_session.py) - Session management
- [Base Router](./base_router.py) - HTTP routing
- [Step Processor](./step_processor.py) - Voice processing
- [Exceptions](./exceptions.py) - Error handling
- [Cache](./cache.py) - Caching utilities

## Support

For issues or questions:
1. Check this guide first
2. Review existing workflows (contact_workflow)
3. Check error logs
4. Create an issue with reproduction steps