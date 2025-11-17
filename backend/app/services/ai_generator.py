# app/services/ai_generator.py
import os
import json
import re
import tempfile
from typing import List, Dict, Optional

# Try to import Gemini client if available
try:
    import google.generativeai as genai
except Exception:
    genai = None

# PDF text extraction (optional - PyPDF2)
try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", 60))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")  # default local Ollama
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")  # local model name for Ollama
USE_OLLAMA_FALLBACK = os.environ.get("USE_OLLAMA_FALLBACK", "1").lower() in ("1", "true", "yes")

if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# -------------------- helpers --------------------
def _extract_json_from_text(text: str) -> Optional[str]:
    """Robustly extract a JSON object/array from text output."""
    # prefer fenced JSON blocks
    m = re.search(r"```(?:json)?\s*([\[\{].*[\]\}])\s*```", text, flags=re.S)
    if m:
        return m.group(1)
    # otherwise take first {...} or [...] block
    m2 = re.search(r"([\[\{].*[\]\}])", text, flags=re.S)
    if m2:
        return m2.group(1)
    return None


def _safe_parse_json(js: str):
    """Try to parse JSON with a few heuristics to fix minor issues."""
    try:
        return json.loads(js)
    except Exception:
        # common fixes
        try:
            fixed = js.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            try:
                fixed2 = re.sub(r",\s*([\]\}])", r"\1", js)  # trailing commas
                return json.loads(fixed2)
            except Exception as e:
                raise RuntimeError(f"Failed to parse JSON: {e}")


# -------------------- PDF extraction --------------------
def extract_text_from_pdf(path: str) -> str:
    """Extract text from a PDF using PyPDF2 (if available)."""
    if not PdfReader:
        raise RuntimeError("PyPDF2 is not installed. Install with: pip install PyPDF2")
    try:
        reader = PdfReader(path)
        pages = []
        for p in reader.pages:
            pages.append(p.extract_text() or "")
        return "\n\n".join(pages)
    except Exception as e:
        raise RuntimeError(f"Failed to read PDF: {e}")


# -------------------- Gemini implementation --------------------
def _call_gemini(system: str, user: str, model: Optional[str] = None) -> str:
    if not genai or not GEMINI_API_KEY:
        raise RuntimeError("Gemini SDK not configured. Set GEMINI_API_KEY or use Ollama fallback.")
    model = model or GEMINI_MODEL
    try:
        client = genai.GenerativeModel(model)
        prompt = f"{system}\n\n{user}"
        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.15,
                max_output_tokens=1500,
            ),
        )
        if response and response.text:
            return response.text
        return str(response)
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}")


# -------------------- Ollama (local) implementation --------------------
def _call_ollama(prompt: str, model: Optional[str] = None) -> str:
    """
    Call a local Ollama server at OLLAMA_HOST.
    Expects Ollama to be running (ollama serve).
    Response handling differs between Ollama versions; we try sensible defaults.
    """
    import requests

    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {"model": model, "prompt": prompt}
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        # Ollama's JSON shape may vary; try common keys
        if isinstance(data, dict):
            if "response" in data:
                return data["response"]
            if "text" in data:
                return data["text"]
            # some versions return 'choices' similar to OpenAI
            choices = data.get("choices")
            if choices and isinstance(choices, list) and len(choices) > 0:
                first = choices[0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"]
                return str(first)
        return json.dumps(data)
    except Exception as e:
        raise RuntimeError(f"Ollama call failed: {e}")


# -------------------- Main generator --------------------
def generate_quiz_with_openai(
    title: str,
    topic: str,
    difficulty: str = "any",
    num_questions: int = 5,
    source_text: Optional[str] = None,
    model_override: Optional[str] = None,
) -> List[Dict]:
    """
    Produce a list of question dicts. Uses Gemini if API key present; otherwise tries Ollama.
    Each question dict: {text, option_a, option_b, option_c, option_d, correct_option, explanation}
    """
    system_prompt = (
        "You are an expert exam writer and pedagogue. Produce EXACTLY a single JSON array of multiple-choice questions only — no commentary, no markdown fences, no extra text. "
        "Each array item must be a JSON object with keys: text, option_a, option_b, option_c, option_d, correct_option, explanation. "
        "correct_option must be 'a','b','c', or 'd' (lowercase). Return exactly one JSON array and nothing else."
    )

    if source_text:
        user_prompt = (
            f"Generate {num_questions} multiple-choice questions for a quiz titled '{title}' on the topic '{topic}'. "
            f"Difficulty: {difficulty}. Base the questions strictly on the source text provided and do not invent facts. "
            "If the source does not contain enough material, return fewer items rather than unrelated content.\n\n"
            "SOURCE:\n" + (source_text[:12000])
        )
    else:
        user_prompt = (
            f"Generate {num_questions} multiple-choice questions for a quiz titled '{title}' on the topic '{topic}'. "
            f"Difficulty: {difficulty}. Return EXACTLY a JSON array where each item looks like: "
            '{"text":"...","option_a":"...","option_b":"...","option_c":"...","option_d":"...","correct_option":"b","explanation":"..."}'
        )

    # Try Gemini if configured
    assistant_text = None
    if genai and GEMINI_API_KEY:
        try:
            assistant_text = _call_gemini(system_prompt, user_prompt, model=model_override)
        except Exception as e:
            # don't abort yet, try Ollama fallback if available
            assistant_text = None
            print(f"[ai_generator] Gemini call failed: {e} — will try Ollama fallback if available.")
    
    # Try Ollama if Gemini failed or USE_OLLAMA_FALLBACK is enabled
    if assistant_text is None and USE_OLLAMA_FALLBACK:
        try:
            full_prompt = system_prompt + "\n\n" + user_prompt
            assistant_text = _call_ollama(full_prompt, model=model_override)
        except Exception as e:
            # If Ollama also fails, raise the error
            raise RuntimeError(f"No available model could be called: Gemini unavailable, Ollama fallback failed: {e}")
    
    # If still no response and neither was attempted, raise error
    if assistant_text is None:
        raise RuntimeError("No available model configured. Set GEMINI_API_KEY or enable USE_OLLAMA_FALLBACK with OLLAMA_HOST configured.")

    json_text = _extract_json_from_text(assistant_text) or assistant_text
    parsed = _safe_parse_json(json_text)
    if not isinstance(parsed, list):
        raise RuntimeError("AI returned JSON but it is not a list")

    # Normalize items
    out = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or ""
        opts = {
            "option_a": item.get("option_a") or item.get("a") or "",
            "option_b": item.get("option_b") or item.get("b") or "",
            "option_c": item.get("option_c") or item.get("c") or "",
            "option_d": item.get("option_d") or item.get("d") or "",
        }
        corr = (item.get("correct_option") or item.get("answer") or "").strip().lower()
        explanation = item.get("explanation") or ""

        if corr not in ("a", "b", "c", "d"):
            corr = corr[:1] if corr and corr[0] in "abcd" else "a"

        out.append({
            "text": text.strip(),
            "option_a": opts["option_a"].strip(),
            "option_b": opts["option_b"].strip(),
            "option_c": opts["option_c"].strip(),
            "option_d": opts["option_d"].strip(),
            "correct_option": corr,
            "explanation": explanation.strip(),
        })

    # Trim to requested number
    if len(out) > num_questions:
        out = out[:num_questions]
    return out


def generate_quiz_from_file(file_path: str, title: str, topic: str, difficulty: str = "any", num_questions: int = 5, model_override: Optional[str] = None) -> List[Dict]:
    """Extract text from the uploaded file and call the generator."""
    text = extract_text_from_pdf(file_path)
    if not text.strip():
        raise RuntimeError("Uploaded file produced no extractable text.")
    return generate_quiz_with_openai(title=title, topic=topic, difficulty=difficulty, num_questions=num_questions, source_text=text, model_override=model_override)
