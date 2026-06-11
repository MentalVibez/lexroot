from ingestor.research_triage_agent import (
    ResourceInput,
    classify_topics,
    report_payload,
    triage_resource,
)


def test_book_defaults_to_metadata_only_and_editor_review():
    record = triage_resource(
        ResourceInput(
            title="A Book of Middle English",
            creator="J.A. Burrow and Thorlac Turville-Petre",
            type="book",
        )
    )

    assert record.type == "book"
    assert record.access_type == "library"
    assert record.license_use_status == "metadata only"
    assert "Middle English" in record.topic_tags
    assert record.review_status == "needs human review"
    assert any("Do not store copyrighted body text" in warning for warning in record.warnings)


def test_public_podcast_is_link_only_resource_card():
    record = triage_resource(
        ResourceInput(
            title="Lingthusiasm Podcast",
            creator="Gretchen McCulloch and Lauren Gawne",
            type="podcast",
            url="https://lingthusiasm.com/",
        )
    )

    assert record.access_type == "public"
    assert record.license_use_status == "link only"
    assert record.recommended_site_use == "resource card"
    assert record.safe_use_note.startswith("Link to the show")


def test_robot_disallow_marks_manual_link_only_warning():
    record = triage_resource(
        ResourceInput(
            title="Example Site",
            type="website",
            url="https://example.com/research",
        ),
        robots_allowed=False,
    )

    assert record.robots_allowed is False
    assert any("robots.txt disallows" in warning for warning in record.warnings)


def test_topic_classifier_marks_major_language_layers():
    assert classify_topics("Greek and Latin in English Today", "book") == ["Latin/Greek"]
    assert "Indo-European" in classify_topics("The American Heritage Dictionary of Indo-European Roots", "reference")
    assert "alphabet" in classify_topics("ABC et Cetera: The Life and Times of the Roman Alphabet", "book")


def test_report_payload_contains_guardrails_not_body_text():
    record = triage_resource(ResourceInput(title="The Etymologicon", type="book"))
    payload = report_payload([record])

    assert payload["record_count"] == 1
    assert any("No copyrighted body text" in guardrail for guardrail in payload["guardrails"])
    assert "records" in payload
