from tools.airtable import build_content_table_definition


def test_content_table_definition_contains_required_fields() -> None:
    payload = build_content_table_definition()
    names = {field["name"] for field in payload["fields"]}
    required = {
        "Ad Name",
        "Product",
        "Image Prompt",
        "Image Status",
        "Generated Image",
        "Video Prompt",
        "Video Status",
        "Generated Video",
        "Prompt JSON",
        "Prompt Schema",
        "Provider Used",
        "Estimated Cost",
        "Actual Cost",
        "Batch ID",
        "Generation Error",
        "Convexe Insight Source",
    }
    assert required.issubset(names)
