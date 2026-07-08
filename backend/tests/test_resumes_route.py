def test_upload_resume_returns_generated_id(client, sample_resume):
    response = client.post("/resumes", json=sample_resume)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["resume_id"], str)
    assert body["resume_id"]


def test_each_upload_gets_a_unique_id(client, sample_resume):
    first = client.post("/resumes", json=sample_resume)
    second = client.post("/resumes", json=sample_resume)

    assert first.json()["resume_id"] != second.json()["resume_id"]
