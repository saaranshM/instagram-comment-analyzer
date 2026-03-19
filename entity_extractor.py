"""Domain-agnostic entity extractor using GLiNER + fuzzy dictionary."""

import os
import re
import sys
from gliner import GLiNER
from rapidfuzz import fuzz
from taxonomy import Taxonomy

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "gliner_multi-v2.1")
_CLEAN_WORD_RE = re.compile(r'[^\w]', re.UNICODE)


def _clean_words(text):
    return [_CLEAN_WORD_RE.sub('', w) for w in text.lower().split() if _CLEAN_WORD_RE.sub('', w)]


class EntityExtractor:
    """Hybrid NER extractor: GLiNER zero-shot + fuzzy dictionary matching.

    Accepts a Taxonomy instance to work with any domain (cars, phones, sneakers, etc.).
    The GLiNER model is loaded once and shared across all EntityExtractor instances.
    """

    _shared_model = None

    @classmethod
    def _load_model(cls):
        if cls._shared_model is not None:
            return cls._shared_model
        print("Loading GLiNER model...", file=sys.stderr)
        if os.path.isdir(_MODEL_DIR) and os.path.exists(os.path.join(_MODEL_DIR, "gliner_config.json")):
            cls._shared_model = GLiNER.from_pretrained(_MODEL_DIR, local_files_only=True)
        else:
            print("  Local model not found, downloading from HuggingFace...", file=sys.stderr)
            cls._shared_model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        print("Model loaded.", file=sys.stderr)
        return cls._shared_model

    def __init__(self, taxonomy):
        self.taxonomy = taxonomy
        self.model = self._load_model()
        self.labels = taxonomy.gliner_labels
        self.lookup_table = taxonomy.build_lookup_table()
        self.reject_words = taxonomy.reject_words
        self.strip_prefixes = taxonomy.strip_prefixes

    def _fuzzy_match(self, text):
        text_lower = text.lower()
        words = _clean_words(text)
        matches = set()

        for alias, group, item in self.lookup_table:
            alias_len = len(alias)
            if alias_len <= 4:
                if alias in words:
                    matches.add((group, item))
                continue

            if " " in alias:
                alias_words = alias.split()
                if not all(
                    any(fuzz.ratio(aw, tw) >= 80 for tw in words)
                    for aw in alias_words
                    if len(aw) > 1
                ):
                    continue
                matches.add((group, item))
                continue

            score = fuzz.partial_ratio(alias, text_lower)
            threshold = 88 if alias_len <= 6 else 80
            if score >= threshold:
                matches.add((group, item))

        return matches

    def _gliner_extract(self, text):
        entities = self.model.predict_entities(text, self.labels, threshold=0.5)
        matches = set()

        for entity in entities:
            entity_text = entity["text"].lower().strip()

            if entity_text in self.reject_words:
                continue

            cleaned = entity_text
            for prefix in self.strip_prefixes:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):]
                    break

            if cleaned in self.reject_words or len(cleaned) < 3:
                continue

            best_match = None
            best_score = 0
            for alias, group, item in self.lookup_table:
                score = fuzz.ratio(cleaned, alias)
                if score > best_score and score >= 82:
                    best_score = score
                    best_match = (group, item)

            if best_match:
                matches.add(best_match)
            else:
                if len(cleaned) > 4 and cleaned not in self.reject_words:
                    matches.add((cleaned.title(), None))

        return matches

    def _merge(self, fuzzy_matches, gliner_matches):
        all_matches = fuzzy_matches | gliner_matches
        groups_with_items = {g for g, item in all_matches if item is not None}
        return {(g, item) for g, item in all_matches
                if item is not None or g not in groups_with_items}

    def extract(self, comments):
        results = []
        total = len(comments)
        for i, comment in enumerate(comments):
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  Analyzing comment {i + 1}/{total}...", file=sys.stderr)
            text = comment.get("text", "")
            if not text:
                continue

            fuzzy_matches = self._fuzzy_match(text)
            gliner_matches = self._gliner_extract(text)
            all_matches = self._merge(fuzzy_matches, gliner_matches)

            for group, item in all_matches:
                results.append({
                    "brand": group,
                    "model": item,
                    "source_comment": text,
                    "username": comment.get("username", ""),
                    "comment_like_count": comment.get("like_count", 0),
                })

        return results


class RawExtractor:
    """GLiNER-only extractor — no taxonomy needed.

    Extracts entities using only zero-shot NER with user-provided labels.
    No fuzzy dictionary, no normalization, no reject words.
    Use when you want quick extraction without defining a taxonomy.
    """

    def __init__(self, labels):
        self.model = EntityExtractor._load_model()
        self.labels = labels

    def extract(self, comments):
        results = []
        total = len(comments)
        for i, comment in enumerate(comments):
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  Analyzing comment {i + 1}/{total}...", file=sys.stderr)
            text = comment.get("text", "")
            if not text:
                continue

            entities = self.model.predict_entities(text, self.labels, threshold=0.5)
            seen = set()
            for entity in entities:
                entity_text = entity["text"].strip()
                label = entity["label"]
                key = (entity_text.lower(), label)
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "entity": entity_text,
                    "label": label,
                    "confidence": round(entity["score"], 3),
                    "source_comment": text,
                    "username": comment.get("username", ""),
                    "comment_like_count": comment.get("like_count", 0),
                })

        return results
