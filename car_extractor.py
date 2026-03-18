import sys
from gliner import GLiNER
from rapidfuzz import fuzz
from car_dictionary import CAR_DATABASE, build_lookup_table


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
        matches = set()

        words = text_lower.split()
        for alias, brand, model in self.lookup_table:
            alias_len = len(alias)
            # Very short aliases (e.g., "mg", "vw", "byd", "tata", "kia", "benz")
            # must appear as an exact word to avoid false positives
            if alias_len <= 4:
                if alias in words:
                    matches.add((brand, model))
                continue

            # Use partial_ratio for substring matching (handles "brezza plz")
            score = fuzz.partial_ratio(alias, text_lower)
            threshold = 85 if alias_len <= 6 else 75
            if score >= threshold:
                matches.add((brand, model))

        return matches

    def _gliner_extract(self, text):
        """Extract car entities using GLiNER zero-shot NER."""
        entities = self.model.predict_entities(text, self.labels, threshold=0.5)
        matches = set()

        for entity in entities:
            entity_text = entity["text"].lower().strip()
            # Try to map GLiNER entity to our dictionary
            best_match = None
            best_score = 0
            for alias, brand, model in self.lookup_table:
                score = fuzz.ratio(entity_text, alias)
                if score > best_score and score >= 70:
                    best_score = score
                    best_match = (brand, model)

            if best_match:
                matches.add(best_match)
            else:
                # GLiNER found something not in our dictionary — keep it as-is
                matches.add((entity_text.title(), None))

        return matches

    def _merge(self, fuzzy_matches, gliner_matches):
        """Union of both match sets, deduplicated."""
        return fuzzy_matches | gliner_matches

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
