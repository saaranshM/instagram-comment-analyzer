"""Backward-compatible wrapper — CarExtractor using cars taxonomy."""

import os
from taxonomy import Taxonomy
from entity_extractor import EntityExtractor

_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomies", "cars.yaml")


class CarExtractor(EntityExtractor):
    def __init__(self):
        super().__init__(Taxonomy(_TAXONOMY_PATH))
