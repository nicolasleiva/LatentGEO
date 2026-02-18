file_path = r"c:\Users\Dell\auditor_geo\auditor_geo\backend\app\integrations\github\nextjs_modifier.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Finding the prompt definition
start_marker = 'prompt = f"""'
end_marker = '"""'

start_idx = content.find(start_marker)
if start_idx == -1:
    print("Could not find start marker")
    exit(1)

start_content = start_idx + len(start_marker)
end_idx = content.find(end_marker, start_content)
fstring_body = content[start_content:end_idx]

print(f"Analyzing f-string body of length {len(fstring_body)}")

# Search for {faq...} pattern
# In f-string, {{ is literal {, { is start of expression.
# We look for single { followed by 'faq'

# We can iterate and count braces
i = 0
length = len(fstring_body)
while i < length:
    if fstring_body[i] == "{":
        if i + 1 < length and fstring_body[i + 1] == "{":
            # Double brace {{ -> skip both
            i += 2
            continue
        else:
            # Single brace { -> check content
            # find matching }
            j = i + 1
            depth = 1
            while j < length and depth > 0:
                if fstring_body[j] == "{":
                    depth += 1
                elif fstring_body[j] == "}":
                    depth -= 1
                j += 1

            expr = fstring_body[i + 1 : j - 1]
            print(f"Found expression: {{{expr}}}")

            if "faq" in expr:
                print(f"!!! PROBLEM CANDIDATE: {{{expr}}}")

            i = j
    else:
        i += 1
