import json
import sys


def log(severity: str, message: str, **fields) -> None:
    """One JSON object per line. Cloud Logging reads 'severity' and 'message' automatically."""
    print(json.dumps({"severity": severity, "message": message, **fields}, default=str), file=sys.stdout, flush=True)
