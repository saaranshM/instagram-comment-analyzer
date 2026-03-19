def filter_comments(comments, text=None):
    """Pre-filter: keep only comments matching a text substring."""
    if text:
        text_lower = text.lower()
        return [c for c in comments if text_lower in c["text"].lower()]
    return comments


def filter_results(results, brand=None, item=None, car=None):
    """Post-filter: filter extracted results by brand or item (model).

    'car' is a backward-compat alias for 'item'.
    """
    if brand:
        brand_lower = brand.lower()
        results = [r for r in results if brand_lower in r["brand"].lower()]
    item_filter = item or car
    if item_filter:
        item_lower = item_filter.lower()
        results = [r for r in results if r["model"] and item_lower in r["model"].lower()]
    return results
