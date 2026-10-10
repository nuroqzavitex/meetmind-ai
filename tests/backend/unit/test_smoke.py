from app.ai.errors import AnalysisError, LLMError, LLMRefusal


def test_error_hierarchy():
    assert issubclass(LLMRefusal, LLMError)
    e = AnalysisError("boom", step="extract")
    assert e.step == "extract" and "boom" in str(e)
