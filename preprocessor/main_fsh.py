import argparse
import csv
import re
from collections import Counter

from bs4 import BeautifulSoup

# Argument parsing
parser = argparse.ArgumentParser(description="Tag FSH files with keyword extensions.")
parser.add_argument("source", help="Path to the input FSH file")
parser.add_argument("destination", help="Path to the output FSH file")
parser.add_argument(
    "--keywords", default="keywords.csv", help="CSV file with keyword metadata"
)

args = parser.parse_args()

source_path = args.source
destination_path = args.destination
file = "/Users/joaoalmeida/Desktop/hl7Europe/gravitate/gravitate-health/input/fsh/examples/rawEPI/amox-ema-automatic/composition-en-b62cc095c7be2116a8a65157286376a3.fsh"
# Define keywords and highlight classes

keywords = {
    "diabetes": {
        "class": "diabetes",
        "code": "DB01234",
        "system": "snomed",
        "display": "METFORMIN",
    },
    "children": {
        "class": "children",
        "code": "DB99999",
        "system": "snomed",
        "display": "PARACETAMOL",
    },
    "rash": {
        "class": "rash",
        "code": "DB99998",
        "system": "snomed",
        "display": "PARACETAMOL",
    },
    "elderly": {
        "class": "jonwort",
        "code": "DB00099",
        "system": "snomed",
        "display": "HYPERICUM",
    },
    "Adults": {
        "class": "jonwort",
        "code": "DB00099",
        "system": "snomed",
        "display": "HYPERICUM",
    },
    "hepatitis B": {
        "class": "jonwort",
        "code": "66071002",
        "system": "snomed",
        "display": "Viral hepatitis type B (disorder)",
    },
}
# Load keywords from CSV

with open(args.keywords, newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile, delimiter=";")
    for row in reader:
        print(row)
        keyword = row["keyword"].strip()
        keywords[keyword] = {
            "class": row["class"].strip(),
            "system": row["system"].strip(),
            "code": row["code"].strip(),
            "display": row["display"].strip(),
        }


# Count matches
keyword_counter = Counter()


def tag_deepest_elements(html: str, keywords: dict) -> str:
    soup = BeautifulSoup(html, "lxml")
    known_classes = [v["class"] for v in keywords.values()]

    def matches_keyword(tag_text):
        matches = []
        tag_text_lower = tag_text.lower()
        for word, data in keywords.items():
            if word.lower() in tag_text_lower:
                matches.append((word, data["class"]))
        return matches

    for tag in reversed(soup.find_all(["li", "p", "span", "div"])):
        # Skip if any child already has one of the classes
        if tag.find(
            attrs={
                "class": lambda c: c and any(cls in c.split() for cls in known_classes)
            }
        ):
            continue

        tag_text = tag.get_text(strip=True)
        matches = matches_keyword(tag_text)

        for keyword, css_class in matches:
            keyword_counter[keyword] += 1
            existing_classes = tag.get("class", [])
            if css_class not in existing_classes:
                tag["class"] = existing_classes + [css_class]

    return str(soup)


# Load FSH
with open(source_path, "r", encoding="utf-8") as f:
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
tagged = []
for keyword, count in keyword_counter.items():
    if keyword not in keywords:
        continue

    data = keywords[keyword]
    css_class = data["class"]
    code = data["code"]
    display = data["display"]
    system = data["system"]
    if code + display + system + css_class not in tagged:
        extension_lines.extend(
            [
                '* extension[+].url = "http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/HtmlElementLink"',
                '* extension[=].extension[+].url = "elementClass"',
                f'* extension[=].extension[=].valueString = "{css_class}"',
                '* extension[=].extension[+].url = "concept"',
                f'* extension[=].extension[=].valueCodeableReference.concept.coding = {system}#{code} "{display}"',
                "",
            ]
        )
        tagged.append(code + display + system + css_class)


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
with open(destination_path, "w", encoding="utf-8") as f:
    f.write(fsh_content)

# --- Print keyword stats ---
print("✅ Keyword counts:")
for word, count in keyword_counter.items():
    print(f"  {word}: {count}")
