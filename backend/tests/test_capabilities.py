import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.mark.parametrize("key,configured", [(None, False), ("", False), ("  ", False),
                                           ("test-only-not-a-provider-key", True)])
def test_capabilities_are_safe_configuration_metadata(monkeypatch, key, configured):
    if key is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_KEY", key)

    def forbidden(*args, **kwargs):
        raise AssertionError("Capabilities must not access the database or AI provider")

    monkeypatch.setattr(main, "SessionLocal", forbidden)
    monkeypatch.setattr(main, "answer_filing_question", forbidden)
    monkeypatch.setattr("app.answer_service._get_openai_client", forbidden)
    response = TestClient(main.app).get("/capabilities")
    assert response.status_code == 200
    assert response.json() == {"research_mode": True, "ai_analysis_configured": configured}
    if key and key.strip():
        assert key not in response.text
