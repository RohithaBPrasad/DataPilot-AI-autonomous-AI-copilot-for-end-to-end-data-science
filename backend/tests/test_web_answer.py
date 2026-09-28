from backend.app.services.web_answer import extract_answer_from_web_result


def test_extract_answer_from_web_result_uses_abstract_text():
    result = {
        "Answer": "",
        "AbstractText": "The capital of France is Paris.",
        "RelatedTopics": [{"Text": "France is a country in Europe."}],
    }

    answer = extract_answer_from_web_result(result)

    assert "Paris" in answer
    assert "capital of France" in answer.lower()


def test_extract_answer_from_web_result_falls_back_to_top_related_topic():
    result = {
        "Answer": "",
        "AbstractText": "",
        "RelatedTopics": [{"Text": "Python is a programming language."}],
    }

    answer = extract_answer_from_web_result(result)

    assert "Python" in answer
    assert "programming language" in answer.lower()
