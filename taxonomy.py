"""Taxonomy loading and registry for domain-agnostic entity extraction."""

import os
import json
import yaml


class Taxonomy:
    """Represents a loaded entity taxonomy (cars, phones, sneakers, etc.)."""

    def __init__(self, source):
        """Load taxonomy from a YAML/JSON file path or a raw dict."""
        if isinstance(source, str):
            with open(source, "r", encoding="utf-8") as f:
                if source.endswith(".json"):
                    raw = json.load(f)
                else:
                    raw = yaml.safe_load(f)
        elif isinstance(source, dict):
            raw = source
        else:
            raise ValueError(f"Taxonomy source must be a file path or dict, got {type(source)}")

        meta = raw.get("taxonomy", {})
        if not meta.get("id"):
            raise ValueError("Taxonomy must have 'taxonomy.id' field")
        if not meta.get("domain"):
            raise ValueError("Taxonomy must have 'taxonomy.domain' field")

        self._meta = meta
        self._entities = raw.get("entities", {})
        if not self._entities:
            raise ValueError("Taxonomy must have non-empty 'entities' section")

        self._lookup_table = None

    @property
    def id(self):
        return self._meta["id"]

    @property
    def name(self):
        return self._meta.get("name", self.id)

    @property
    def domain(self):
        return self._meta["domain"]

    @property
    def group_label(self):
        return self._meta.get("group_label", "brand")

    @property
    def item_label(self):
        return self._meta.get("item_label", "model")

    @property
    def gliner_labels(self):
        if "gliner_labels" in self._meta:
            return self._meta["gliner_labels"]
        return [
            f"{self.domain} {self.group_label}",
            f"{self.domain} {self.item_label}",
            self.domain,
        ]

    @property
    def reject_words(self):
        return set(self._meta.get("reject_words", []))

    @property
    def strip_prefixes(self):
        return self._meta.get("strip_prefixes", ["new ", "old "])

    @property
    def database(self):
        return self._entities

    @property
    def group_count(self):
        return len(self._entities)

    @property
    def item_count(self):
        return sum(len(g.get("models", {})) for g in self._entities.values())

    def build_lookup_table(self):
        """Build a flat lookup table: [(alias, group_name, item_name), ...]"""
        if self._lookup_table is not None:
            return self._lookup_table

        lookup = []
        for group_name, group_data in self._entities.items():
            for alias in group_data.get("aliases", []):
                lookup.append((alias, group_name, None))
            for item_name, aliases in group_data.get("models", {}).items():
                for alias in aliases:
                    lookup.append((alias, group_name, item_name))

        self._lookup_table = lookup
        return lookup


class TaxonomyRegistry:
    """Discovers and manages multiple taxonomies from a directory."""

    def __init__(self, taxonomy_dir=None):
        self._taxonomies = {}
        if taxonomy_dir and os.path.isdir(taxonomy_dir):
            self.load_directory(taxonomy_dir)

    def load_file(self, path):
        t = Taxonomy(path)
        self._taxonomies[t.id] = t
        return t

    def load_directory(self, dir_path):
        for fname in sorted(os.listdir(dir_path)):
            if fname.endswith((".yaml", ".yml", ".json")):
                try:
                    self.load_file(os.path.join(dir_path, fname))
                except (ValueError, yaml.YAMLError, json.JSONDecodeError) as e:
                    print(f"Warning: Failed to load taxonomy {fname}: {e}")

    def get(self, taxonomy_id):
        if taxonomy_id not in self._taxonomies:
            raise KeyError(f"Taxonomy '{taxonomy_id}' not found. Available: {', '.join(self.list_ids())}")
        return self._taxonomies[taxonomy_id]

    def list_ids(self):
        return list(self._taxonomies.keys())

    def default(self):
        if "cars" in self._taxonomies:
            return self._taxonomies["cars"]
        if self._taxonomies:
            return next(iter(self._taxonomies.values()))
        raise ValueError("No taxonomies loaded")

    def reload(self, taxonomy_dir):
        self._taxonomies.clear()
        self.load_directory(taxonomy_dir)
