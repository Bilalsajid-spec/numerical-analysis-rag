# Purpose: entry point for asking questions about the notes.
# Work: accept a question, retrieve relevant chunks, and display an answer with sources.

import argparse
import json
import sys
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from rag_nm.pipeline import ask
from rag_nm.generation import LocalGenerator


def display(result):
    print("\n" + result["answer"])
    for number, source in enumerate(result["sources"], 1):
        print(f"\n[{number}] {source['source']} | PDF page {source['page']}")
        if result["mode"] == "retrieval":
            print(source["text"])
    if result.get("truncated"):
        print("\n[Answer reached its output limit; inspect the sources for the complete explanation.]")
    if result.get("citation_warning"):
        print("\n[The model did not add inline citations; the retrieved sources are listed above.]")


def main():
    parser = argparse.ArgumentParser(description="Ask your numerical analysis notes, fully locally")
    parser.add_argument("question", nargs="?", help="Omit for interactive questions")
    parser.add_argument("--retrieve-only", action="store_true", help="Show evidence without loading the answer model")
    parser.add_argument("--week", type=int, help="Filter by a positive week number in the PDF filenames")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--json", action="store_true", help="Machine-readable output for one question")
    args = parser.parse_args()
    if args.json and not args.question:
        parser.error("--json requires a question")
    # Reuse the model process throughout the interactive session and close it on exit.
    try:
        with LocalGenerator() as generator:
            if args.question:
                print("Searching your notes...", file=sys.stderr, flush=True)
                result = ask(args.question, generator, args.top_k, args.week, args.retrieve_only)
                print(json.dumps(result, ensure_ascii=False, indent=2)) if args.json else display(result)
                return
            print("Numerical Analysis RAG | type exit to close | ask standalone questions about your indexed notes")
            while True:
                question = input("\nYou: ").strip()
                if question.lower() in {"exit", "quit"}:
                    break
                if question:
                    print("Searching your notes...", file=sys.stderr, flush=True)
                    display(ask(question, generator, args.top_k, args.week, args.retrieve_only))
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as error:
        parser.exit(1, f"Error: {error}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nSession closed.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
