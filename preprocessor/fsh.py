import argparse
import csv
import re
from collections import Counter, defaultdict

import textstat
from bs4 import BeautifulSoup

READABILITY_THRESHOLD = 20  # Ex: Flesch Reading Ease: the lower, the harder it is.
READABILITY_LENGTH_THRESHOLD = 100
DIFFICULT_CLASS = "difficult"
DIFFICULTY_EXTENSION = {
    "class": DIFFICULT_CLASS,
    "code": "diff001",
    "system": "local",
    "display": "Difficult text",
}

# Argument parsing
parser = argparse.ArgumentParser(description="Tag FSH files with keyword extensions.")
parser.add_argument("source", help="Path to the input FSH file")
parser.add_argument("destination", help="Path to the output FSH file")
parser.add_argument("bundle", help="Path to a FHIR Bundle FSH file")

parser.add_argument(
    "--keywords", default="keywords.csv", help="CSV file with keyword metadata"
)


args = parser.parse_args()

source_path = args.source
destination_path = args.destination

# Define keywords and highlight classes
DICTWORD = {"icpc-2": "https://icpc2.icd.com/", "snomed": "$sct"}


# Load keywords from CSV


def extract_and_patch_bundles(
    bundlepath, composition_id, new_composition_id_suffix="-pproc"
):
    """
    Extracts and patches bundle blocks referencing the given composition ID.
    Returns the updated bundle blocks.
    """
    # print(bundlepath, composition_id)
    with open(bundlepath, "r", encoding="utf-8") as bundle_file:
        bundle_content = bundle_file.read()

    blocks = re.split(r"(?=^Instance:\s+\S+)", bundle_content, flags=re.MULTILINE)
    patched_bundles = []

    for block in blocks:
        if not block.strip():
            continue

        # Only handle Bundles that reference the composition
        if "InstanceOf: Bundle" in block or "InstanceOf: BundleUvEpi" in block:
            if composition_id in block:
                # Extract original Instance name
                match = re.match(r"Instance:\s+(\S+)", block)
                if match:
                    original_instance = match.group(1)
                    new_instance = f"{original_instance}{new_composition_id_suffix}"

                    # Replace Instance name
                    block = re.sub(
                        rf"^Instance:\s+{re.escape(original_instance)}",
                        f"// originally: {original_instance}\nInstance: {new_instance}",
                        block,
                        flags=re.MULTILINE,
                    )

                    # Replace Composition reference inside the bundle
                    block = block.replace(
                        f"= {composition_id}",
                        f"= {composition_id}{new_composition_id_suffix}",
                    )

                    block = block.replace(
                        f"/Composition/{composition_id}",
                        f"/Composition/{composition_id}{new_composition_id_suffix}",
                    )
                    patched_bundles.append(block.strip())

    return patched_bundles


with open(args.keywords, newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile, delimiter=";")
    keywords = defaultdict(dict)  # Ensures keywords[lang] is always a dict

    for row in reader:
        concept_metadata = {
            "class": row["class"].strip(),
            "code": row["code"].strip(),
            "system": row["system"].strip(),
            "display": row["display"].strip(),
        }

        # Go through all columns and find those starting with "keyword_"
        for col in row:
            if col.startswith("keyword_"):
                lang = col.split("_")[1]
                keyword = row[col].strip()
                if keyword:
                    keywords[lang][keyword] = concept_metadata
# Count matches
keyword_counter = Counter()

to_explain = []


def tag_deepest_elements(
    html: str, keywords: dict, create_plain_language: bool = False
) -> str:
    idx = 0
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

        # Check readability difficulty
        if (
            tag_text
            and textstat.flesch_reading_ease(tag_text) < READABILITY_THRESHOLD
            and len(tag_text) > READABILITY_LENGTH_THRESHOLD
        ):
            idx += 1
            #   print(textstat.flesch_reading_ease(tag_text))
            matches.append(("difficult_text", DIFFICULT_CLASS))
            if create_plain_language:
                matches.append(("plain-language", "plain-language-" + str(idx)))
                to_explain.append(("plain-language-" + str(idx), tag_text))

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
language = re.findall(r"\* language = \#(\w{2})\n", fsh_content)[0]
print(language)
if language in ["en", "da", "pt", "es"]:
    # print(keywords[language])
    for start, html, end in matches:
        html_tagged = tag_deepest_elements(html.strip(), keywords[language])
        fsh_content = fsh_content.replace(
            f"{start}{html}{end}", f"{start}\n{html_tagged}\n{end}"
        )
else:
    raise "no language!!"
# --- Modify Instance name ---
instance_match = re.search(r"^Instance:\s*(\S+)", fsh_content, flags=re.MULTILINE)
if instance_match:
    original_name = instance_match.group(1)
    new_name = f"{original_name}-pproc"
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
    if keyword not in keywords[language]:
        continue

    data = keywords[language][keyword]
    css_class = data["class"]
    code = data["code"]
    display = data["display"]
    system = data["system"]
    formated_system = DICTWORD.get(system, system)

    if code + display + system + css_class not in tagged:
        extension_lines.extend(
            [
                '* extension[+].url = "http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/HtmlElementLink"',
                '* extension[=].extension[+].url = "elementClass"',
                f'* extension[=].extension[=].valueString = "{css_class}"',
                '* extension[=].extension[+].url = "concept"',
                f'* extension[=].extension[=].valueCodeableReference.concept.coding = {formated_system}#{code} "{display}"',
                "",
            ]
        )
        tagged.append(code + display + system + css_class)

## explain language
for x in to_explain:
    print(x)

    # response = explaining_plain_language(x[1])
    response = x[1]
    extension_lines.extend(
        [
            '* extension[+].url = "http://hl7.eu/fhir/ig/gravitate-health/StructureDefinition/AdditionalInformation"',
            '* extension[=].extension[+].url = "elementClass"',
            f"* extension[=].extension[=].valueString = {x[0]}",
            '* extension[=].extension[+].url = "type"',
            '* extension[=].extension[=].valueCodeableConcept.coding[0].system = "http://hl7.eu/fhir/ig/gravitate-health/CodeSystem/type-of-data-cs"',
            "* extension[=].extension[=].valueCodeableConcept.coding[0].code = #TXT",
            '* extension[=].extension[=].valueCodeableConcept.coding[0].display = "Text"',
            '* extension[=].extension[+].url = "concept"',
            f"* extension[=].extension[=].valueString = {response}",
            "",
        ]
    )
# if anything added, create preproc
if len(extension_lines) > 0:
    # Combine extension lines into a single string block
    extension_block = (
        "\n// Auto-tagged extensions\n" + "\n".join(extension_lines) + "\n"
    )

    # Find the position of the first section line
    section_match = re.search(r"^(\* section\[\+\].*)", fsh_content, flags=re.MULTILINE)

    if section_match:
        insert_position = section_match.start()
        fsh_content = (
            fsh_content[:insert_position]
            + extension_block
            + fsh_content[insert_position:]
        )
    else:
        print(
            "⚠️ Warning: No '* section[+]' line found. Appending extension block to the end."
        )
        fsh_content += extension_block

    patched_bundles = extract_and_patch_bundles(args.bundle, original_name)
    print(patched_bundles)
    if patched_bundles:
        fsh_content += "\n\n// Referenced and patched Bundle Instances\n" + "\n\n".join(
            patched_bundles
        )
    # Save updated FSH
    with open(destination_path, "w", encoding="utf-8") as f:
        f.write(fsh_content)

    # --- Print keyword stats ---
    print("✅ Keyword counts:")
    for word, count in keyword_counter.items():
        print(f"  {word}: {count}")
else:
    print("⚠️ Warning: No extensions found. ")
