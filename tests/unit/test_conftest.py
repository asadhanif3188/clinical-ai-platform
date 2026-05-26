import pytest


@pytest.mark.asyncio
async def test_fixtures_smoke(
    mock_settings,
    mock_anthropic,
    db_session,
    redis_mock,
    sample_lab_report_state,
    sample_medication_list,
):
    assert mock_settings.anthropic_api_key == "test-key"
    assert mock_anthropic is not None
    assert db_session is not None
    assert redis_mock is not None
    assert sample_lab_report_state["document_type"] == "lab_report"
    assert len(sample_medication_list) == 2
