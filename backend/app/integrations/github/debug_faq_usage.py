import re

file_path = r"c:\Users\Dell\auditor_geo\auditor_geo\backend\app\integrations\github\nextjs_modifier.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Regex to find single Open Brace followed by 'faq'
# We want {faq but NOT {{faq
# Regex: (?<!\{)\{faq
# We also want to avoid matches where it is just text?
# But in a python file, {faq could be in an f-string or just a dict, or set.
# If it is in a dict/set, 'faq' would be a variable.
# If it is in a string "...", it is just text.
# If it is in f"...", it is a variable.

# So finding any usage of {faq as a VARIABLE or Expression is key.

matches = [m for m in re.finditer(r"(?<!\{)\{faq", content)]
print(f"Found {len(matches)} occurrences of single-brace faq")

for m in matches:
    # Context
    start = max(0, m.start() - 20)
    end = min(len(content), m.end() + 20)
    print(f"Match at {m.start()}: ...{content[start:end]}...")

    # Check if inside f-string
    # Simple heuristic: scan backwards for f" or f"""
    # This is not perfect but might give a clue.
