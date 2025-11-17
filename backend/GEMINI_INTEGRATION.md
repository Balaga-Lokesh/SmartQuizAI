# Gemini API Integration Summary

## Overview
Successfully replaced OpenAI API with Google Gemini API throughout the SmartQuizAI backend. The system now uses Gemini as the primary AI model with Ollama as a configurable fallback.

## Changes Made

### 1. Backend Service (`app/services/ai_generator.py`)
- **Replaced**: `import openai` → `import google.generativeai as genai`
- **Updated Config**:
  - `OPENAI_API_KEY` → `GEMINI_API_KEY`
  - `OPENAI_MODEL` → `GEMINI_MODEL` (default: `gemini-1.5-flash`)
  - `OPENAI_TIMEOUT` → `GEMINI_TIMEOUT_SECONDS`
  - Added `USE_OLLAMA_FALLBACK` env var (default: `1` = enabled)
- **Updated Functions**:
  - `_call_openai_chat()` → `_call_gemini()` - Uses Gemini API directly
  - `generate_quiz_with_openai()` - Now calls Gemini first, then Ollama if fallback enabled
- **Ollama Fallback**: Enabled by default via `USE_OLLAMA_FALLBACK=1` env var

### 2. Dependencies (`requirements.txt`)
- **Removed**: `openai`, `passlib[bcrypt]`
- **Added**: 
  - `google-generativeai` (main Gemini SDK)
  - `PyPDF2` (for PDF text extraction)
  - Kept `passlib[bcrypt]` for password hashing (not removed)

### 3. Environment Configuration
- **`.env` file**: Updated with Gemini and Ollama settings
- **`.env.example`**: Created as template for developers

#### New Environment Variables:
```bash
# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TIMEOUT_SECONDS=60

# Ollama Configuration (Local LLM Fallback)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral
USE_OLLAMA_FALLBACK=1  # Set to 0 to disable Ollama fallback
```

### 4. Testing (`tests/test_ai_generator.py`)
- Created unit tests for Gemini API integration
- Tests verify JSON parsing, question generation, and field validation
- Ollama fallback test (skipped if Ollama not running)

## How It Works

### Primary Flow: Gemini API
```
User Request → Gemini API → Parse JSON → Return Quiz Questions
```

### Fallback Flow: Ollama (if enabled)
```
User Request → Try Gemini → Fails → Try Ollama → Parse JSON → Return Quiz Questions
```

### Configuration
- **Production Mode**: Set `GEMINI_API_KEY` with valid key, `USE_OLLAMA_FALLBACK=0`
- **Development Mode**: Use placeholder `GEMINI_API_KEY` or invalid key, `USE_OLLAMA_FALLBACK=1` to test Ollama locally
- **Local LLM Only**: Leave `GEMINI_API_KEY` empty/invalid, set `USE_OLLAMA_FALLBACK=1`

## API Endpoints
All endpoints using quiz generation continue to work unchanged:
- `POST /api/v1/quizzes/generate` - Uses Gemini (or Ollama fallback)
- `POST /api/v1/quizzes/generate-from-file` - Uses Gemini (or Ollama fallback)

## Testing the Integration

### 1. Quick Test (requires valid Gemini API key)
```bash
cd backend
$env:GEMINI_API_KEY='your-actual-key'
& './venv/Scripts/python.exe' -m pytest tests/test_ai_generator.py::test_generate_quiz_with_gemini_basic -v
```

### 2. Test Ollama Fallback (requires Ollama running locally)
```bash
# Start Ollama first: ollama serve
# Then:
$env:USE_OLLAMA_FALLBACK='1'
& './venv/Scripts/python.exe' -m pytest tests/test_ai_generator.py::test_generate_quiz_fallback_to_ollama -v
```

### 3. Integration Test via API
```bash
# Make sure backend is running with valid Gemini key:
# POST http://localhost:8000/api/v1/quizzes (with uploaded file)
```

## Troubleshooting

### "API_KEY_INVALID" Error
- The Gemini API key in `.env` is placeholder or expired
- Get a valid key from: https://aistudio.google.com/
- Update `GEMINI_API_KEY` in `.env`

### Ollama Connection Failed (404)
- Ollama is not running locally
- Start Ollama: `ollama serve`
- Ensure `OLLAMA_HOST=http://localhost:11434` is correct
- If you don't want to use Ollama, set `USE_OLLAMA_FALLBACK=0`

### No Response from Generation
- Check uvicorn logs for "Gemini call failed" message
- Verify GEMINI_API_KEY is set and valid
- If using Ollama fallback, ensure Ollama is running with a model: `ollama pull mistral`

## Backend Restart Required
After updating `.env` or installing new packages, restart the backend:
```bash
# If uvicorn is running in terminal, press Ctrl+C
# Then restart with:
cd backend
$env:GEMINI_API_KEY='your-key'  # If not in .env
& './venv/Scripts/python.exe' -m uvicorn app.main:app --reload
```

## Files Modified
1. `backend/app/services/ai_generator.py` - Gemini API integration
2. `backend/requirements.txt` - Dependency updates
3. `backend/.env` - Configuration update
4. `backend/.env.example` - Template creation
5. `backend/tests/test_ai_generator.py` - Unit tests

## Function Signature (unchanged for API consumers)
```python
def generate_quiz_with_openai(
    title: str,
    topic: str,
    difficulty: str = "any",
    num_questions: int = 5,
    source_text: Optional[str] = None,
    model_override: Optional[str] = None,
) -> List[Dict]:
    """Returns list of question dicts with Gemini or Ollama."""
```

*Note: Function name kept as `generate_quiz_with_openai` for backward compatibility with existing imports.*

## Next Steps
1. Update GEMINI_API_KEY in `.env` with a valid Google Gemini API key
2. Test the integration by running the unit tests
3. Deploy to production with proper environment variables
