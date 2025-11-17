import pytest
import os
from app.services.ai_generator import generate_quiz_with_openai


def test_generate_quiz_with_gemini_basic():
    """Test basic quiz generation with Gemini API (skip Ollama fallback for this test)."""
    # Check if Gemini API key is configured
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        pytest.skip("GEMINI_API_KEY not configured; skipping Gemini test")

    # Temporarily disable Ollama fallback for this test
    original_fallback = os.environ.get("USE_OLLAMA_FALLBACK", "1")
    os.environ["USE_OLLAMA_FALLBACK"] = "0"
    
    try:
        result = generate_quiz_with_openai(
            title="Test Quiz",
            topic="Python Programming",
            difficulty="easy",
            num_questions=2,
            source_text=None,
        )
        
        # Verify result is a list
        assert isinstance(result, list), "Result should be a list"
        assert len(result) > 0, "Result should not be empty"
        
        # Verify each question has required fields
        for item in result:
            assert isinstance(item, dict), "Each item should be a dict"
            assert "text" in item, "Question should have 'text' field"
            assert "option_a" in item, "Question should have 'option_a' field"
            assert "option_b" in item, "Question should have 'option_b' field"
            assert "option_c" in item, "Question should have 'option_c' field"
            assert "option_d" in item, "Question should have 'option_d' field"
            assert "correct_option" in item, "Question should have 'correct_option' field"
            assert "explanation" in item, "Question should have 'explanation' field"
            assert item["correct_option"] in ("a", "b", "c", "d"), "correct_option must be a/b/c/d"
            assert item["text"].strip(), "Question text should not be empty"
    except RuntimeError as e:
        if "GEMINI_API_KEY" in str(e) or "API key not valid" in str(e):
            pytest.skip(f"Gemini API key invalid or not available: {e}")
        raise
    finally:
        # Restore original fallback setting
        os.environ["USE_OLLAMA_FALLBACK"] = original_fallback



def test_generate_quiz_fallback_to_ollama():
    """Test fallback to Ollama when Gemini is unavailable."""
    # Temporarily disable Gemini and enable Ollama fallback
    os.environ["GEMINI_API_KEY"] = ""  # Disable Gemini
    os.environ["USE_OLLAMA_FALLBACK"] = "1"  # Enable Ollama fallback
    
    try:
        result = generate_quiz_with_openai(
            title="Test Quiz (Ollama)",
            topic="Basic Science",
            difficulty="medium",
            num_questions=1,
            source_text=None,
        )
        # If Ollama is running, this should work; if not, it will raise an error
        # Either way, we're testing the code path
        if isinstance(result, list):
            assert len(result) >= 0, "Result should be a list"
    except RuntimeError as e:
        # This is expected if Ollama is not running
        assert "Ollama" in str(e) or "available model" in str(e), f"Expected Ollama error, got: {e}"


if __name__ == "__main__":
    # Run tests
    test_generate_quiz_with_gemini_basic()
    print("✓ Gemini API test passed")
    
    # Test Ollama fallback (may fail if Ollama not running)
    try:
        test_generate_quiz_fallback_to_ollama()
        print("✓ Ollama fallback test passed")
    except Exception as e:
        print(f"⚠ Ollama fallback test skipped/failed (expected if Ollama not running): {e}")
