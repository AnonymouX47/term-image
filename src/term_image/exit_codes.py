"""Exit codes for fatal errors"""

from __future__ import annotations

codes = {
    0: "SUCCESS",
    1: "FAILURE",
    2: "INVALID_ARG",
    3: "INTERRUPTED",
    4: "NO_VALID_SOURCE",
}

globals().update((v, k) for k, v in codes.items())
