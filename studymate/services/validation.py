"""Validate untrusted model output before it reaches persistence or the UI.

These checks verify shape and reference membership, not semantic truth.
"""

from .provider import ProviderError


def object_value(value):
    if not isinstance(value, dict):
        raise ProviderError("AI 응답 항목은 객체여야 합니다.")
    return value


def string_value(value, maximum=20000, allow_empty=False):
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (not allow_empty and not value.strip())
    ):
        raise ProviderError("AI 응답의 텍스트 형식을 확인할 수 없습니다.")
    return value


def string_list(value, maximum=100):
    if not isinstance(value, list) or len(value) > maximum:
        raise ProviderError("AI 응답의 목록 형식을 확인할 수 없습니다.")
    for item in value:
        string_value(item)
    return value


def source_ids(value, allowed, required=True):
    ids = string_list(value)
    if (required and not ids) or not set(ids) <= set(allowed):
        raise ProviderError(
            "AI 결과의 출처를 확인할 수 없습니다. 결과를 저장하지 않았습니다."
        )
    return ids


def learning_result(value, kind, sources):
    object_value(value)
    allowed = {s["id"] for s in sources}
    if "title" in value:
        string_value(value["title"], 200)
    field = {
        "summary": "sections",
        "quiz": "questions",
        "concepts": "edges",
        "terms": "terms",
    }[kind]
    entries = value.get(field)
    maximum = {"summary": 21, "quiz": 20, "concepts": 100, "terms": 25}[kind]
    if (
        not isinstance(entries, list)
        or len(entries) > maximum
        or (kind != "terms" and not entries)
    ):
        raise ProviderError("AI 결과에 필요한 항목이 없거나 허용 수를 초과했습니다.")
    for item in entries:
        object_value(item)
        ids = source_ids(item.get("source_ids"), allowed)
        if kind == "summary":
            string_value(item.get("text"))
            string_value(item.get("heading", ""), 500, allow_empty=True)
        elif kind == "quiz":
            for key in ("question", "answer"):
                string_value(item.get(key))
            choices = string_list(item.get("options"), 4)
            if (
                len(choices) != 4
                or len(set(choices)) != 4
                or item["answer"] not in choices
                or item.get("kind") != "multiple_choice"
            ):
                raise ProviderError("객관식 선택지와 정답을 확인할 수 없습니다.")
            for key in ("explanation", "concept"):
                string_value(item.get(key, ""), allow_empty=True)
        elif kind == "concepts":
            for key in ("from", "to", "label"):
                string_value(item.get(key), 500)
            string_value(item.get("condition", ""), allow_empty=True)
        else:
            word = string_value(item.get("word"), 120)
            string_value(item.get("meaning", ""), 2000, allow_empty=True)
            string_value(item.get("pronunciation", ""), 200, allow_empty=True)
            string_list(item.get("related", []), 10)
            if not any(
                word.casefold() in s["text"].casefold()
                for s in sources
                if s["id"] in ids
            ):
                raise ProviderError("추출한 용어를 인용된 원문에서 찾을 수 없습니다.")
    if kind == "concepts":
        nodes = value.get("nodes")
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 10:
            raise ProviderError("개념도 노드 형식 오류")
        node_ids = []
        for node in nodes:
            object_value(node)
            node_ids.append(string_value(node.get("id"), 500))
            string_value(node.get("label"), 500)
        if len(set(node_ids)) != len(node_ids) or any(
            e["from"] not in node_ids or e["to"] not in node_ids for e in entries
        ):
            raise ProviderError("개념도 연결 형식 오류")
    return entries
