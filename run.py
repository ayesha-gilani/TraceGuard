
import argparse
import json
import sys

from traceguard.ingestion import load_jsonl
from traceguard.repository import EventRepository
from traceguard.investigator import investigate


def main():
    parser = argparse.ArgumentParser(
        description="TraceGuard - Payment Incident Investigation System"
    )

    parser.add_argument("--events", required=True, help="Path to JSONL events")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--order", required=True, help="Order ID")
    parser.add_argument("--question", required=True, help="Investigation question")

    args = parser.parse_args()

    events, ingestion_issues = load_jsonl(args.events)

    # Only report ingestion issues relevant to the requested scope
    # when the malformed line cannot be associated with another order.
    repository = EventRepository(events)

    result = investigate(
        repository,
        tenant_id=args.tenant,
        order_id=args.order,
    )

    output = result.to_dict()

    output["question"] = args.question
    output["ingestion_issues"] = [
        issue.to_dict() for issue in ingestion_issues
    ]

    print(json.dumps(output, indent=2))

    if ingestion_issues:
        print(
            f"\nWarning: {len(ingestion_issues)} ingestion issue(s) found.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
