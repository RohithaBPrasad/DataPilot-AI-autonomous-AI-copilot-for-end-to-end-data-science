from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "EvolveDataScienceAgent/1.0"
NO_ANSWER = "I couldn't find a reliable answer online right now. Please try asking the question with a little more detail."


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_answer_from_web_result(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""

    for key in ("Answer", "AbstractText"):
        text = _clean_text(str(result.get(key, "") or ""))
        if text:
            return text

    for topic in result.get("RelatedTopics", []) or []:
        if isinstance(topic, dict):
            text = _clean_text(str(topic.get("Text") or topic.get("Result") or topic.get("Name") or ""))
            if text:
                return text
        elif isinstance(topic, str):
            text = _clean_text(topic)
            if text:
                return text

    for item in result.get("Results", []) or []:
        if isinstance(item, dict):
            text = _clean_text(str(item.get("Text") or item.get("Result") or item.get("Name") or ""))
            if text:
                return text

    return ""


def _request_json(url: str) -> dict[str, Any] | list[Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"})
    with urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8", errors="replace")


def _python_code_answer(query: str) -> str:
    lowered = query.lower()
    if not any(term in lowered for term in ("python", "code", "function", "program", "script")):
        return ""

    if "even" in lowered and "odd" in lowered:
        return (
            "Here is a complete Python function that checks whether a number is even or odd:\n\n"
            "```python\n"
            "def check_even_or_odd(number: int) -> str:\n"
            "    return \"even\" if number % 2 == 0 else \"odd\"\n\n"
            "number = int(input(\"Enter a number: \"))\n"
            "print(f\"{number} is {check_even_or_odd(number)}\")\n"
            "```\n\n"
            "The modulo operator (`%`) returns the remainder after division by 2. "
            "A remainder of 0 means the number is even; otherwise it is odd."
        )
    return ""


def _live_news_answer(query: str) -> str:
    lowered = query.lower()
    news_terms = ("latest", "live", "news", "headline", "current events", "today")
    if not any(term in lowered for term in news_terms):
        return ""

    topic = re.sub(
        r"\b(what|is|are|the|latest|live|news|headlines?|around|about|today|current|events)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    topic = re.sub(r"\s+", " ", topic).strip() or "world"
    feeds = [
        (
            f"Google News search: {topic}",
            f"https://news.google.com/rss/search?q={quote(topic)}&hl=en-US&gl=US&ceid=US:en",
        ),
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/world/rss"),
    ]
    articles: list[str] = []
    for source, url in feeds[:1]:
        try:
            root = ElementTree.fromstring(_request_text(url))
        except Exception:
            continue
        for item in root.findall(".//item")[:4]:
            title = _clean_text(item.findtext("title", ""))
            link = item.findtext("link", "")
            published = _clean_text(item.findtext("pubDate", ""))
            if title and link:
                if source.startswith("Google News"):
                    title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
                date = f" ({published})" if published else ""
                articles.append(f"- {title}{date}\n  {link}\n  Source: {source}")

    if not articles:
        for source, url in feeds[1:]:
            try:
                root = ElementTree.fromstring(_request_text(url))
            except Exception:
                continue
            for item in root.findall(".//item")[:4]:
                title = _clean_text(item.findtext("title", ""))
                link = item.findtext("link", "")
                published = _clean_text(item.findtext("pubDate", ""))
                if title and link:
                    date = f" ({published})" if published else ""
                    articles.append(f"- {title}{date}\n  {link}\n  Source: {source}")

    if not articles:
        return ""
    return "Live news headlines from current RSS feeds:\n\n" + "\n\n".join(articles[:8])


def _wikipedia_answer(query: str) -> str:
    normalized_query = re.sub(r"\btamilnadu\b", "Tamil Nadu", query, flags=re.IGNORECASE)
    normalized_query = re.sub(r"^who\s+is\s+(the\s+)?", "", normalized_query, flags=re.IGNORECASE)
    normalized_query = re.sub(r"\s+", " ", normalized_query).strip()
    search_url = (
        "https://en.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={quote(normalized_query)}&srlimit=3&format=json"
    )
    search_payload = _request_json(search_url)
    if not isinstance(search_payload, dict):
        return ""

    results = search_payload.get("query", {}).get("search", [])
    sections: list[str] = []
    for item in results[:3]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
        try:
            summary = _request_json(summary_url)
        except Exception:
            continue
        if not isinstance(summary, dict):
            continue
        extract = _clean_text(str(summary.get("extract", "")))
        page_url = summary.get("content_urls", {}).get("desktop", {}).get("page")
        if extract:
            source = f" Source: {page_url}" if page_url else ""
            sections.append(f"{title}: {extract}{source}")

    return "\n\n".join(sections)


def _wikidata_current_office_holder(query: str) -> str:
    normalized_query = re.sub(r"\btamilnadu\b", "Tamil Nadu", query, flags=re.IGNORECASE)
    if "chief minister" not in normalized_query.lower() or "tamil" not in normalized_query.lower():
        return ""

    search_url = (
        "https://www.wikidata.org/w/api.php?action=wbsearchentities"
        f"&search={quote('Chief Minister of Tamil Nadu')}&language=en&limit=1&format=json"
    )
    search_payload = _request_json(search_url)
    if not isinstance(search_payload, dict) or not search_payload.get("search"):
        return ""

    office_id = search_payload["search"][0].get("id")
    if not office_id:
        return ""
    entity_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={quote(office_id)}&languages=en&format=json"
    entity_payload = _request_json(entity_url)
    entity = entity_payload.get("entities", {}).get(office_id, {}) if isinstance(entity_payload, dict) else {}
    statements = entity.get("claims", {}).get("P1308", [])
    holder_ids = [
        statement.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        for statement in statements
    ]
    holder_id = next((item for item in holder_ids if item), None)
    if not holder_id:
        return ""

    holder_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={quote(holder_id)}&languages=en&format=json"
    holder_payload = _request_json(holder_url)
    holder = holder_payload.get("entities", {}).get(holder_id, {}) if isinstance(holder_payload, dict) else {}
    holder_name = holder.get("labels", {}).get("en", {}).get("value")
    holder_description = holder.get("descriptions", {}).get("en", {}).get("value", "")
    if not holder_name:
        return ""
    return (
        f"According to live Wikidata data, {holder_name} is the current Chief Minister of Tamil Nadu. "
        f"{holder_description}. Source: https://www.wikidata.org/wiki/{holder_id}"
    )


def get_web_answer(question: str) -> str:
    query = (question or "").strip()
    if not query:
        return "Please ask a real question and I'll look for the answer online."

    code_answer = _python_code_answer(query)
    if code_answer:
        return code_answer

    news_answer = _live_news_answer(query)
    if news_answer:
        return news_answer

    answers: list[str] = []

    try:
        direct_answer = ""
        encoded = quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        payload = _request_json(url)
        if isinstance(payload, dict):
            direct_answer = extract_answer_from_web_result(payload)
        if direct_answer:
            answers.append(direct_answer)
    except Exception:
        pass

    try:
        current_holder = _wikidata_current_office_holder(query)
        if current_holder:
            answers.append(current_holder)
    except Exception:
        pass

    try:
        wikipedia_answer = _wikipedia_answer(query)
        if wikipedia_answer:
            answers.append(wikipedia_answer)
    except Exception:
        pass

    if answers:
        return "\n\n".join(answers[:3])
    return NO_ANSWER
