"""Blog categories. Keep ids in sync with frontend/lib/categories.js."""

BLOG_CATEGORIES = [
    ("technology", "Technology"),
    ("career", "Career & Growth"),
    ("design", "Design & Creativity"),
    ("lifestyle", "Lifestyle"),
    ("travel", "Travel"),
    ("health", "Health & Wellness"),
    ("business", "Business & Finance"),
    ("education", "Education"),
    ("food", "Food & Cooking"),
    ("personal", "Personal Stories"),
]

CATEGORY_IDS = [cid for cid, _ in BLOG_CATEGORIES]
