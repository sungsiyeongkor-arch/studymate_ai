from studymate.extensions import db
from studymate.models import ReviewState


def test_objective_score_is_server_computed_and_idempotent(app, client):
    lecture = client.setup_lecture()
    card = client.send(
        "POST",
        "/cards",
        {
            "lecture_id": lecture["id"],
            "question": "2 + 2?",
            "answer": "4",
            "options": ["3", "4", "5"],
        },
    ).json
    state = client.send("GET", "/reviews/due").json["items"][0]["state"]
    payload = {
        "request_key": "objective-1",
        "state_version": state["version"],
        "grade": 3,
        "selected_index": 0,
        "answer": "4",
        "confidence": 2,
    }
    result = client.send("POST", "/cards/" + card["id"] + "/review", payload)
    assert result.status_code == 201
    assert result.json["snapshot"]["correct"] is False
    assert result.json["answer"] == "3"
    assert result.json["grade"] == 0
    assert (
        client.send("GET", "/reviews/mistakes").json["items"][0]["card"]["id"]
        == card["id"]
    )
    assert (
        client.send("POST", "/cards/" + card["id"] + "/review", payload).json["id"]
        == result.json["id"]
    )
    with app.app_context():
        state = ReviewState.query.one()
        version = state.version
    correct = client.send(
        "POST",
        "/cards/" + card["id"] + "/review",
        {
            **payload,
            "request_key": "objective-2",
            "state_version": version,
            "selected_index": 1,
        },
    )
    assert correct.json["snapshot"]["correct"] is True
    assert client.send("GET", "/reviews/mistakes").json["items"] == []


def test_invalid_choices_are_rejected(client):
    lecture = client.setup_lecture()
    response = client.send(
        "POST",
        "/cards",
        {
            "lecture_id": lecture["id"],
            "question": "Q",
            "answer": "not an option",
            "options": ["a", "b"],
        },
    )
    assert response.status_code == 400
