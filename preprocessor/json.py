import json

from bs4 import BeautifulSoup
from fhir.resources.bundle import Bundle
from fhir.resources.composition import Composition

file = "/Users/joaoalmeida/Desktop/hl7Europe/gravitate/gravitate-health/fsh-generated/resources/Bundle-bundlepackageleaflet-en-b62cc095c7be2116a8a65157286376a3.json"
# ✅ Define your keywords and corresponding classes
keywords = {
    "diabetes": "highlight-diabetes",
    "pregnancy": "highlight-pregnancy",
    "hypertension": "highlight-hypertension",
    "children": "highlight-children",
}


def tag_deepest_elements(html: str, keywords: dict) -> str:
    soup = BeautifulSoup(html, "lxml")

    def matches_keyword(tag_text):
        for word, css_class in keywords.items():
            if word.lower() in tag_text.lower():
                return word, css_class
        return None, None

    # Traverse from deepest to top to prioritize inner elements
    for tag in reversed(soup.find_all(["li", "p", "span", "div"])):
        # Skip if any child already tagged
        if tag.find(
            attrs={
                "class": lambda c: c
                and any(cls.startswith("highlight-") for cls in c.split())
            }
        ):
            continue

        tag_text = tag.get_text(strip=True)
        matched_word, css_class = matches_keyword(tag_text)
        if matched_word:
            current_classes = tag.get("class", [])
            if css_class not in current_classes:
                tag["class"] = current_classes + [css_class]

    return str(soup)


# 📄 Load your Bundle
with open(file, "r", encoding="utf-8") as f:
    data = json.load(f)

bundle = Bundle.parse_obj(data)

# 🔍 Find the Composition
composition = next(
    (
        entry.resource
        for entry in bundle.entry
        if isinstance(entry.resource, Composition)
    ),
    None,
)

if not composition:
    raise ValueError("No Composition resource found in the bundle.")

# 🧠 Tag each section
for section in composition.section[0].section:
    if section.text and section.text.div:
        original_div = section.text.div
        tagged_div = tag_deepest_elements(original_div, keywords)
        section.text.div = tagged_div

# 💾 Save updated Bundle
with open("bundle_tagged.json", "w", encoding="utf-8") as f:
    f.write(bundle.json(indent=2))
