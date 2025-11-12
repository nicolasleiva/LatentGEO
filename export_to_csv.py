import json
import csv
import sys

if len(sys.argv) < 2:
    print("Usage: python export_to_csv.py <fix_plan_file.json>")
    sys.exit(1)

fix_plan_file = sys.argv[1]
csv_file = fix_plan_file.replace(".json", ".csv")

with open(fix_plan_file, "r", encoding="utf-8") as f:
    fix_plan = json.load(f)

headers = [
    "page_path",
    "issue_code",
    "priority",
    "description",
    "snippet",
    "suggestion_type",
    "suggestion_details",
]

with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    for task in fix_plan:
        suggestion = task.get("suggestion", {})
        writer.writerow(
            {
                "page_path": task.get("page_path"),
                "issue_code": task.get("issue_code"),
                "priority": task.get("priority"),
                "description": task.get("description"),
                "snippet": task.get("snippet", ""),
                "suggestion_type": suggestion.get("type", ""),
                "suggestion_details": json.dumps(
                    suggestion
                ),  # Vuelca el resto de la sugerencia
            }
        )

print(f"¡Exportado! Se creó el archivo {csv_file}")
