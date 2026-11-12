"""Source-grounded, deterministic Topic -> Fact retrieval for the course KG/RAG demo.

This is NOT medical diagnosis, semantic search, or a generative LLM. Only facts
retrieved from Neo4j (with HTTPS source URLs) are quoted in the answer.
No model weights, Neo4j schema, or existing API response keys are changed.
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from services.neo4j_service import Neo4jKnowledgeRepository


class KnowledgeQueryError(ValueError):
    pass


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def validate_question(question: Any) -> str:
    if not isinstance(question, str) or not (3 <= len(question.strip()) <= 500):
        raise KnowledgeQueryError('question must be a string of 3..500 characters')
    question = question.strip()
    if not normalize(question):
        raise KnowledgeQueryError('question contains no searchable words')
    return question


STOPWORDS = {'la','gi','ve','toi','muon','biet','cho','hoi','co','nhung','mot','va','o',
             'cua','di','nay','the','nao','khi','khong','duoc','nhu','nhieu','lam','bao',
             'benh','duong','tieu','dai','thao', 'lien', 'quan', 'den', 'anh', 'huong', 'lam', 'cach', 'nao', 'tac', 'dong'}
# Frequent filler words do not distinguish one Fact from another.
FACT_STOPWORDS = STOPWORDS | {
    'nguoi','mac','can','nen','neu','thi','voi','trong','duoi','tren','that','su',
    'phai','hay','hoac','nao','sao','tai','vi','sau','truoc','khoang','tung',
    'nguon','them','cac','nhat','dang','duoc','loai','tinh','trang',
}
# Limited expression normalization for *retrieval*, not new medical claims.
# These expansions only help find already-authored, sourced facts.
QUERY_EXPANSIONS = {
    'gao lut': 'ngu coc nguyen hat',
    'an chuoi': 'trai cay nguyen qua',
    'an tao': 'trai cay nguyen qua',
    'hoa qua': 'trai cay',
    'tut duong': 'ha duong huyet',
    'duong mau': 'duong huyet',
    'tap gym': 'van dong',
    'tap the duc': 'hoat dong the chat',
    'bieu hien': 'dau hieu',
    'trieu chung': 'bieu hien',
    'dau hieu': 'bieu hien',
}
NO_EVIDENCE = 'Không tìm thấy thông tin phù hợp trong Knowledge Graph hiện tại.'


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(phrase) and f' {phrase} ' in f' {text} '


def _aliases(topic: dict) -> list[str]:
    values = [topic.get('name', ''), *(topic.get('aliases') or [])]
    return [a for a in (normalize(str(value)) for value in values) if a]


def score_topic(query_normalized: str, topic: dict) -> int:
    """Keep P0 topic matching semantics for backward-compatible FAQ coverage."""
    terms = {w for w in query_normalized.split() if len(w) >= 4} - STOPWORDS
    score = 0
    for alias in _aliases(topic):
        if _contains_phrase(query_normalized, alias):
            # A narrowly scoped P1 topic may take priority over a general P0
            # topic; applied ONLY to a complete matching alias.
            priority = topic.get('priority', 0)
            if isinstance(priority, bool) or not isinstance(priority, int):
                priority = 0
            score = max(score, 100 + 12 * len(alias.split()) + max(0, min(100, priority)))
        overlap = len(({w for w in alias.split() if len(w) >= 4} - STOPWORDS) & terms)
        score = max(score, overlap * 18 if overlap >= 2 else 0)
    return score


def _specificity_key(topic: dict) -> tuple[int, str]:
    return (0 if topic.get('category') != 'general' else 1, str(topic.get('id', '')))


def _topic_matches(question: str, topics: list[dict]) -> list[tuple[int, dict]]:
    q = normalize(question)
    scored = [(score_topic(q, topic), topic) for topic in topics]
    scored = [(points, topic) for points, topic in scored if points > 0 and topic.get('id')]
    scored.sort(key=lambda item: (-item[0], *_specificity_key(item[1])))
    specialized = [item for item in scored if item[1].get('category') != 'general']
    if specialized:
        # Do not let generic disease name eclipse an actual question topic.
        scored = specialized
    elif {w for w in q.split() if len(w) >= 4} - STOPWORDS:
        # 'Bệnh tiểu đường và Sao Hỏa' must not return a generic answer.
        return []
    return scored


def _select_topic_ids(question: str, candidates: list[tuple[int, dict]]) -> list[str]:
    if not candidates:
        return []
    chosen = [str(candidates[0][1]['id'])]
    # Use 2 topics only for genuine compound questions, not just for being 2nd
    # in the relevance list. Both must match a complete, topic-specific alias.
    q = normalize(question)
    compound = any(_contains_phrase(q, word) for word in ('va', 'hay', 'khac nhau', 'so sanh', 'voi'))
    # Backward-compatible parent category for the common 'nên uống gì' FAQ:
    # nutrition contains a source-backed water recommendation, too.
    if chosen[0] == 'drinks' and _contains_phrase(q, 'nen uong'):
        if any(topic.get('id') == 'nutrition' for _, topic in candidates[1:]):
            return ['drinks', 'nutrition']
    if not compound:
        return chosen
    leading = candidates[0][0]
    if leading < 110:
        return chosen
    for score, topic in candidates[1:]:
        if score < 110 or score < leading - 24:
            continue
        if not any(_contains_phrase(q, alias) for alias in _aliases(topic)):
            continue
        # Require an additional non-overlapping alias; e.g. 'tăng đường huyết'
        # should not accidentally imply the generic 'đường huyết' topic.
        first_aliases = [a for a in _aliases(candidates[0][1]) if _contains_phrase(q, a)]
        second_aliases = [a for a in _aliases(topic) if _contains_phrase(q, a)]
        if any(not (_contains_phrase(a, b) or _contains_phrase(b, a))
               for a in first_aliases for b in second_aliases):
            chosen.append(str(topic['id']))
            break
    return chosen


def _expanded_query(question: str) -> str:
    text = normalize(question)
    expansions = [expansion for phrase, expansion in QUERY_EXPANSIONS.items()
                  if _contains_phrase(text, phrase)]
    return text + (' ' + ' '.join(expansions) if expansions else '')


def _relevant_tokens(text: str) -> set[str]:
    return {word for word in text.split() if len(word) >= 3 and word not in FACT_STOPWORDS}


def _safe_evidence(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    required = ('fact_id', 'topic_id', 'topic_name', 'text', 'source_id',
                'source_title', 'publisher', 'source_url')
    if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in required):
        return None
    url = raw['source_url'].strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        return None
    return {
        'fact_id': raw['fact_id'], 'topic_id': raw['topic_id'],
        'topic_name': raw['topic_name'], 'excerpt': raw['text'].strip(),
        'source': {'id': raw['source_id'], 'title': raw['source_title'],
                   'publisher': raw['publisher'], 'url': url},
    }


def _rank_facts(question: str, candidates: list[dict]) -> list[dict]:
    expanded = _expanded_query(question)
    q_tokens = _relevant_tokens(expanded)
    tokenized = [_relevant_tokens(normalize(evidence['excerpt'])) for evidence in candidates]
    frequency = Counter(word for tokens in tokenized for word in tokens)
    # Keep meaningful consecutive phrases from the ORIGINAL question, including
    # short expressions such as 'đi bộ' and 'nước ép'.
    raw_words = normalize(question).split()
    raw_q = normalize(question)
    q_pairs = {' '.join(raw_words[i:i+2]) for i in range(len(raw_words)-1)
               if (any(len(w) >= 3 and w not in FACT_STOPWORDS for w in raw_words[i:i+2])
                   or raw_words[i:i+2] == ['di', 'bo'])}

    def fact_score(index: int) -> float:
        tokens = tokenized[index]
        matched = tokens & q_tokens
        # Rare words are more meaningful than repetitive ones (TF-IDF-like).
        score = sum(2.0 + 5.0 / (1 + frequency[word]) for word in matched)
        fact = normalize(candidates[index]['excerpt'])
        score += 7.0 * sum(1 for pair in q_pairs if _contains_phrase(fact, pair))
        # Question asks whether a food is allowed: prioritize cautious facts
        # explaining that food groups are not categorically forbidden.
        if _contains_phrase(raw_q, 'duoc khong') and _contains_phrase(fact, 'khong nhat thiet'):
            score += 10.0
        if (_contains_phrase(raw_q, 'dau hieu') or _contains_phrase(raw_q, 'trieu chung')) and _contains_phrase(fact, 'bieu hien'):
            score += 8.0
            if _contains_phrase(fact, 'bieu hien co the gap'):
                score += 16.0
        return score

    ordered = sorted(range(len(candidates)),
                     key=lambda i: (-fact_score(i), candidates[i]['fact_id']))
    return [candidates[i] for i in ordered]


def _no_evidence(question: str, topics: list[str] | None = None) -> dict:
    return {'question': question, 'answer': NO_EVIDENCE,
            'matched_topics': topics or [], 'retrieved_fact_count': 0,
            'response_kind': 'no_evidence', 'knowledge_version': 'demo-kg-v1.3-p1',
            'retrieval_method': 'topic_fact_lexical_v2'}


class KnowledgeRetrievalService:
    def __init__(self, repository: Neo4jKnowledgeRepository | Any | None = None):
        self.repository = repository if repository is not None else Neo4jKnowledgeRepository()

    def readiness(self) -> str:
        return self.repository.readiness()

    def query(self, raw_question: Any, max_facts: int = 4) -> dict:
        question = validate_question(raw_question)
        if isinstance(max_facts, bool) or not isinstance(max_facts, int) or not 1 <= max_facts <= 8:
            raise KnowledgeQueryError('max_facts must be an integer from 1 to 8')
        ranked_topics = _topic_matches(question, self.repository.list_topics())
        chosen = _select_topic_ids(question, ranked_topics)
        if not chosen:
            return _no_evidence(question)

        # Fetch a pool before selecting the final top 4; never rely on Fact ID order.
        # For compound questions, get enough candidates from *both* topics.
        raw = self.repository.evidence_for_topics(chosen, max(24, max_facts * len(chosen) * 3))
        by_topic = {topic: [] for topic in chosen}
        seen_ids = set()
        for item in raw:
            evidence = _safe_evidence(item)
            if not evidence or evidence['topic_id'] not in by_topic:
                continue
            if evidence['fact_id'] in seen_ids:
                continue
            seen_ids.add(evidence['fact_id'])
            by_topic[evidence['topic_id']].append(evidence)

        if not any(by_topic.values()):
            return _no_evidence(question, chosen)

        # The current KG does not contain medication-specific entries or doses.
        # Do not answer a specific medicine/dosage question with unrelated generic
        # therapy facts merely because a topic alias happened to match.
        q_norm = normalize(question)
        if any(_contains_phrase(q_norm, phrase) for phrase in ('bao nhieu mg', 'lieu dung', 'lieu bao nhieu', 'tu tang lieu')):
            return _no_evidence(question, chosen)
        if _contains_phrase(q_norm, 'metformin') and not any(
                'metformin' in normalize(ev['excerpt']) for rows in by_topic.values() for ev in rows):
            return _no_evidence(question, chosen)

        ranks = {topic: _rank_facts(question, rows) for topic, rows in by_topic.items()}
        chosen_evidence: list[dict] = []
        # For a focused drink question, one supporting nutrition fact is enough;
        # avoid adding unrelated generic meal-plan facts just to fill the quota.
        if chosen == ['drinks', 'nutrition']:
            max_facts = min(max_facts, 3)
        # Round-robin prevents one Topic consuming the entire evidence budget.
        while len(chosen_evidence) < max_facts and any(ranks.values()):
            for topic in chosen:
                if len(chosen_evidence) >= max_facts:
                    break
                if ranks[topic]:
                    chosen_evidence.append(ranks[topic].pop(0))
        if not chosen_evidence:
            return _no_evidence(question, chosen)

        sentences = [f"- {item['excerpt']} [Nguồn {i}]"
                     for i, item in enumerate(chosen_evidence, 1)]
        return {'question': question,
                'answer': 'Thông tin tham khảo từ Knowledge Graph:\n' + '\n'.join(sentences),
                'matched_topics': chosen, 'retrieved_fact_count': len(chosen_evidence),
                'response_kind': 'grounded_extractive', 'knowledge_version': 'demo-kg-v1.3-p1',
                'retrieval_method': 'topic_fact_lexical_v2',
                'source_note': 'Các Nguồn 1..n lần lượt tương ứng với phần evidence của response.',
                '_evidence': chosen_evidence}
