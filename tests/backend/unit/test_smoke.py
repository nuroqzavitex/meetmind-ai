from app.ai.errors import AnalysisError, LLMRefusal, LLMError


def test_error_hierarchy():
    assert issubclass(LLMRefusal, LLMError)
    e = AnalysisError("boom", step="extract")
    assert e.step == "extract" and "boom" in str(e)
