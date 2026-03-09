"""
TEXT PARSE CSV SKILL - Parse CSV data
"""
from canonical_skills.base import Skill, SkillResult, Artifact
import csv
import io


class TextParseCsvSkill(Skill):
    """Parse CSV data into structured format."""

    id = "text_parse_csv"
    version = "1.0.0"
    description = "Parse CSV data into list of dictionaries"

    capabilities = ["parse_csv", "csv_processing", "data_import"]
    requirements = []

    input_schema = {
        "type": "object",
        "properties": {
            "csv_string": {"type": "string", "description": "CSV string to parse"},
            "delimiter": {"type": "string", "description": "CSV delimiter", "default": ","},
            "has_header": {"type": "boolean", "description": "First row is header", "default": True}
        },
        "required": ["csv_string"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "headers": {"type": "array", "items": {"type": "string"}},
            "row_count": {"type": "integer"}
        }
    }

    produces_artifacts = ["KNOWLEDGE", "DATASET"]

    def execute(self, input_data: dict, context: dict) -> SkillResult:
        """Parse CSV string."""
        csv_string = input_data.get("csv_string", "")
        delimiter = input_data.get("delimiter", ",")
        has_header = input_data.get("has_header", True)

        if not csv_string:
            return self._error_result("No CSV string provided")

        try:
            # Parse CSV
            reader = csv.reader(io.StringIO(csv_string), delimiter=delimiter)
            rows = list(reader)

            if not rows:
                return self._error_result("Empty CSV data")

            headers = None
            data_rows = rows

            if has_header and len(rows) > 0:
                headers = rows[0]
                data_rows = rows[1:]

            # Convert to dict format if headers available
            if headers:
                formatted_rows = []
                for row in data_rows:
                    row_dict = {}
                    for i, header in enumerate(headers):
                        row_dict[header] = row[i] if i < len(row) else ""
                    formatted_rows.append(row_dict)
            else:
                formatted_rows = data_rows

            output = {
                "rows": formatted_rows,
                "headers": headers,
                "row_count": len(formatted_rows),
                "column_count": len(headers) if headers else (len(data_rows[0]) if data_rows else 0)
            }

            artifact = self._artifact(
                type_="KNOWLEDGE",
                content=f"Parsed {len(formatted_rows)} rows from CSV",
                metadata={
                    "row_count": len(formatted_rows),
                    "column_count": output["column_count"],
                    "has_headers": has_header
                }
            )

            return self._success_result(output, [artifact])

        except Exception as e:
            return self._error_result(f"CSV parsing failed: {str(e)}")
