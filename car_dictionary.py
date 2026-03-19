"""Backward-compatible wrapper — loads cars taxonomy from YAML."""

import os
from taxonomy import Taxonomy

_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomies", "cars.yaml")
_taxonomy = Taxonomy(_TAXONOMY_PATH)

CAR_DATABASE = _taxonomy.database


def build_lookup_table():
    return _taxonomy.build_lookup_table()
