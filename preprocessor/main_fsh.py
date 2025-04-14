import re
from collections import Counter

from bs4 import BeautifulSoup

file = "/Users/joaoalmeida/Desktop/hl7Europe/gravitate/gravitate-health/input/fsh/examples/rawEPI/amox-ema-automatic/composition-en-b62cc095c7be2116a8a65157286376a3.fsh"
# Define keywords and highlight classes
keywords = {
    "diabetes": "highlight-diabetes",
    "children": "highlight-children",
    "rash": "highlight-rash",
}

# Concept mapping: word → (code, display)
concept_mapping = {
    "diabetes": ("DB01234", "METFORMIN"),
    "pregnancy": ("DB00045", "THALIDOMIDE"),
    "hypertension": ("DB00321", "ENALAPRIL"),
    "children": ("DB99999", "PARACETAMOL"),
    "rash": ("DB99999", "PARACETAMOL"),
}


# Count matches
keyword_counter = Counter()


def tag_deepest_elements(html: str, keywords: dict) -> str:
    soup = BeautifulSoup(html, "lxml")

    def matches_keyword(tag_text):
        for word, css_class in keywords.items():
            if word.lower() in tag_text.lower():
                return word, css_class
        return None, None

    for tag in reversed(soup.find_all(["li", "p", "span", "div"])):
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
            keyword_counter[matched_word] += 1
            existing_class = tag.get("class", [])
            if css_class not in existing_class:
                tag["class"] = existing_class + [css_class]

    return str(soup)


# Load FSH
with open(file, "r", encoding="utf-8") as f:
    fsh_content = f.read()

# --- Update text.div blocks ---
pattern = r'(\* .*?text\.div\s*=\s*""")(.*?)("""\s*)'
matches = re.findall(pattern, fsh_content, flags=re.DOTALL)

for start, html, end in matches:
    html_tagged = tag_deepest_elements(html.strip(), keywords)
    fsh_content = fsh_content.replace(
        f"{start}{html}{end}", f"{start}\n{html_tagged}\n{end}"
    )

# --- Modify Instance name ---
instance_match = re.search(r"^Instance:\s*(\S+)", fsh_content, flags=re.MULTILINE)
if instance_match:
    original_name = instance_match.group(1)
    top_keyword = keyword_counter.most_common(1)[0][0] if keyword_counter else "tagged"
    new_name = f"{original_name}_preprocessed"
    fsh_content = re.sub(
        rf"^Instance:\s*{original_name}",
        f"Instance: {new_name}",
        fsh_content,
        flags=re.MULTILINE,
    )

# --- Add/Replace Composition category ---
category_line = '* category = epicategory-cs#P "Processed"'
if "* category" in fsh_content:
    fsh_content = re.sub(
        r"^\* category.*$", category_line, fsh_content, flags=re.MULTILINE
    )
else:
    # Insert after InstanceOf line
    fsh_content = re.sub(
        r"(^InstanceOf:.*$)", r"\1\n" + category_line, fsh_content, flags=re.MULTILINE
    )

# Add extension block to FSH
extension_lines = []
for keyword, count in keyword_counter.items():
    if keyword not in concept_mapping:
        continue
    code, display = concept_mapping[keyword]
    css_class = keywords[keyword]

    extension_lines.extend(
        [
            '* extension[+].url = "http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/HtmlElementLink"',
            '* extension[=].extension[+].url = "elementClass"',
            f'* extension[=].extension[=].valueString = "{css_class}"',
            '* extension[=].extension[+].url = "concept"',
            f'* extension[=].extension[=].valueCodeableReference.concept.coding = $ginas#{code} "{display}"',
            "",
        ]
    )

# Combine extension lines into a single string block
extension_block = "\n// Auto-tagged extensions\n" + "\n".join(extension_lines) + "\n"

# Find the position of the first section line
section_match = re.search(r"^(\* section\[\+\].*)", fsh_content, flags=re.MULTILINE)

if section_match:
    insert_position = section_match.start()
    fsh_content = (
        fsh_content[:insert_position] + extension_block + fsh_content[insert_position:]
    )
else:
    print(
        "⚠️ Warning: No '* section[+]' line found. Appending extension block to the end."
    )
    fsh_content += extension_block

# Save updated FSH
with open("example_tagged.fsh", "w", encoding="utf-8") as f:
    f.write(fsh_content)

# --- Print keyword stats ---
print("✅ Keyword counts:")
for word, count in keyword_counter.items():
    print(f"  {word}: {count}")
