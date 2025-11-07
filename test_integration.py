#!/usr/bin/env python3
from app.pipeline import run_extraction_pipeline
from app.pdf_parser import parse_pdf
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def test_extraction(pdf_path: str, label: str, schema: dict):
    """Test extraction on a single PDF."""
    print(f"\n{'='*60}")
    print(f"Testing: {pdf_path}")
    print(f"Label: {label}")
    print(f"{'='*60}\n")

    # Parse PDF
    print("1. Parsing PDF...")
    with open(pdf_path, 'rb') as f:
        parse_result = parse_pdf(f)

    print(f"Extracted {len(parse_result['lines'])} lines")
    print(f"Preview: {parse_result['full_text'][:100]}...\n")

    # Run extraction
    print("2. Running extraction pipeline...")
    result = run_extraction_pipeline(
        pdf_lines=parse_result["lines"],
        doc_text=parse_result["full_text"],
        schema=schema,
        label=label,
        timeout_seconds=9.0
    )

    # Display results
    print("\n3. Results:")
    print(f"Metadata: {json.dumps(result['metadata'], indent=2)}")
    print(f"\nExtracted fields:")
    for field, value in result['fields'].items():
        status = "✓" if value else "✗"
        print(f"   {status} {field}: {value}")

    return result


def main():
    """Run tests on dataset."""
    dataset_path = Path("dataset.json")

    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found")
        sys.exit(1)

    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    # Test first entry
    if dataset:
        for entry in dataset:
            pdf_path = f'examples/{entry["pdf_path"]}'
            label = entry["label"]
            schema = entry["extraction_schema"]

            if not Path(pdf_path).exists():
                print(f"Error: PDF not found: {pdf_path}")
                sys.exit(1)

            result = test_extraction(pdf_path, label, schema)

            print(f"\n{'='*60}")
            print("Test completed!")
            print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
