def filter_comments(comments, text=None):
    """Pre-filter: keep only comments matching a text substring."""
    if text:
        text_lower = text.lower()
        return [c for c in comments if text_lower in c["text"].lower()]
    return comments


def filter_results(results, brand=None, car=None):
    """Post-filter: filter extracted car results by brand or model."""
    if brand:
        brand_lower = brand.lower()
        results = [r for r in results if brand_lower in r["brand"].lower()]
    if car:
        car_lower = car.lower()
        results = [r for r in results if r["model"] and car_lower in r["model"].lower()]
    return results
