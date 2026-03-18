import re
import sys
from gliner import GLiNER
from rapidfuzz import fuzz
from car_dictionary import CAR_DATABASE, build_lookup_table

# Common Hindi/English words GLiNER may incorrectly tag as vehicles
GLINER_REJECT_WORDS = {
    # Hindi/Hinglish common words
    "gaadi", "gadi", "bhai", "bro", "please", "video", "next", "sukoon",
    "mast", "dope", "fire", "love", "best", "classic", "super", "great",
    "nice", "cool", "king", "boss", "sir", "level", "edit", "amazing",
    # English common words that aren't cars
    "car", "bike", "vehicle", "city", "sport", "model", "black", "white",
    "grey", "gray", "red", "blue", "silver", "green",
}

# Prefixes GLiNER may attach to car names (strip before matching)
STRIP_PREFIXES = ["new ", "old ", "white ", "black ", "red ", "blue ", "silver ", "grey "]

# Regex to strip punctuation/emojis from words for matching
_CLEAN_WORD_RE = re.compile(r'[^\w]', re.UNICODE)


def _clean_words(text):
    """Split text into words with punctuation stripped (e.g. 'ciaz.' → 'ciaz')."""
    return [_CLEAN_WORD_RE.sub('', w) for w in text.lower().split() if _CLEAN_WORD_RE.sub('', w)]


class CarExtractor:
    def __init__(self):
        print("Loading GLiNER model (first run downloads ~781MB)...", file=sys.stderr)
        self.model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        self.labels = ["car brand", "car model", "vehicle"]
        self.lookup_table = build_lookup_table()
        print("Model loaded.", file=sys.stderr)

    def _fuzzy_match(self, text):
        """Match comment text against car dictionary using fuzzy matching."""
        text_lower = text.lower()
        words = _clean_words(text)
        matches = set()

        for alias, brand, model in self.lookup_table:
            alias_len = len(alias)
            # Very short aliases (<=4 chars) must appear as an exact word
            if alias_len <= 4:
                if alias in words:
                    matches.add((brand, model))
                continue

            # For multi-word aliases, verify ALL significant words appear in the text
            if " " in alias:
                alias_words = alias.split()
                if not all(
                    any(fuzz.ratio(aw, tw) >= 80 for tw in words)
                    for aw in alias_words
                    if len(aw) > 1  # skip single-char words like "r" in "wagon r"
                ):
                    continue
                matches.add((brand, model))
                continue

            # Single-word aliases (5+ chars): use partial_ratio
            score = fuzz.partial_ratio(alias, text_lower)
            threshold = 88 if alias_len <= 6 else 80
            if score >= threshold:
                matches.add((brand, model))

        return matches

    def _gliner_extract(self, text):
        """Extract car entities using GLiNER zero-shot NER."""
        entities = self.model.predict_entities(text, self.labels, threshold=0.5)
        matches = set()

        for entity in entities:
            entity_text = entity["text"].lower().strip()

            # Skip common words that aren't car names
            if entity_text in GLINER_REJECT_WORDS:
                continue

            # Strip color/adjective prefixes ("new baleno" → "baleno")
            cleaned = entity_text
            for prefix in STRIP_PREFIXES:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):]
                    break

            # Skip if cleaned text is a reject word or too short
            if cleaned in GLINER_REJECT_WORDS or len(cleaned) < 3:
                continue

            # Try to map to our dictionary (use cleaned text)
            best_match = None
            best_score = 0
            for alias, brand, model in self.lookup_table:
                score = fuzz.ratio(cleaned, alias)
                if score > best_score and score >= 82:
                    best_score = score
                    best_match = (brand, model)

            if best_match:
                matches.add(best_match)
            else:
                # GLiNER found something not in our dictionary — keep it
                # but only if it's a reasonably specific name
                if len(cleaned) > 4 and cleaned not in GLINER_REJECT_WORDS:
                    matches.add((cleaned.title(), None))

        return matches

    def _merge(self, fuzzy_matches, gliner_matches):
        """Union of both match sets, deduplicated.

        If we have both a brand-only match (model=None) and a model-specific
        match for the same brand, drop the brand-only match.
        """
        all_matches = fuzzy_matches | gliner_matches
        brands_with_models = {brand for brand, model in all_matches if model is not None}
        return {(brand, model) for brand, model in all_matches
                if model is not None or brand not in brands_with_models}

    def extract(self, comments):
        """Extract car mentions from a list of comments.

        Returns list of dicts with brand, model, source_comment, username, comment_like_count.
        """
        results = []
        total = len(comments)
        for i, comment in enumerate(comments):
            if (i + 1) % 50 == 0 or i == 0:
                print(
                    f"  Analyzing comment {i + 1}/{total}...",
                    file=sys.stderr,
                )
            text = comment.get("text", "")
            if not text:
                continue

            fuzzy_matches = self._fuzzy_match(text)
            gliner_matches = self._gliner_extract(text)
            all_matches = self._merge(fuzzy_matches, gliner_matches)

            for brand, model in all_matches:
                results.append(
                    {
                        "brand": brand,
                        "model": model,
                        "source_comment": text,
                        "username": comment.get("username", ""),
                        "comment_like_count": comment.get("like_count", 0),
                    }
                )

        return results
