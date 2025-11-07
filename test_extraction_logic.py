#!/usr/bin/env python3
"""Test extraction logic directly without running the API server."""
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, str(Path(__file__).parent))

from app.pdf_parser import parse_pdf
from app.pipeline import run_extraction_pipeline

def main():
    schema = {
        "nome": "Nome completo da pessoa",
        "inscricao": "Número de inscrição OAB",
        "seccional": "Seccional OAB (estado)",
        "tipo": "Tipo de inscrição",
        "situacao": "Situação cadastral",
        "endereco": "Endereço completo",
        "telefone": "Número de telefone"
    }

    pdf_path = "oab_1.pdf"
    print(f"Parsing PDF: {pdf_path}")

    with open(pdf_path, 'rb') as pdf_file:
        result = parse_pdf(pdf_file)

    print(f"\nExtracted {len(result['lines'])} lines:")
    for idx, line in enumerate(result['lines'][:10]):
        print(f"  Line {idx}: {line['text'][:80]}")

    print("\n" + "="*60)
    print("Running extraction pipeline...")
    print("="*60 + "\n")

    extracted = run_extraction_pipeline(
        pdf_lines=result['lines'],
        doc_text=result['full_text'],
        schema=schema,
        label="oab",
        timeout_seconds=9.0
    )

    print("\nExtracted Fields:")
    print("="*60)
    for field, value in extracted['fields'].items():
        print(f"  {field:15} = {value}")
    print("="*60)

    print(f"\nMetadata:")
    print(f"  Total fields: {extracted['metadata']['total_fields']}")
    print(f"  Extracted: {extracted['metadata']['extracted_fields']}")
    print(f"  Uncertain: {len(extracted['metadata']['uncertain_fields'])}")
    if extracted['metadata']['uncertain_fields']:
        print(f"  Uncertain fields: {', '.join(extracted['metadata']['uncertain_fields'])}")

if __name__ == "__main__":
    main()
