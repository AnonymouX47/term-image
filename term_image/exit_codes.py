"""Exit codes for fatal errors"""

from __future__ import annotations

codes = {
    0: "SUCCESS",
    1: "FAILURE",
    # Omit bash shell exit code 2
    3: "INTERRUPTED",
    4: "CONFIG_ERROR",
    5: "NO_VALID_SOURCE",
    6: "INVALID_ARG",
}

globals().update(((v, k) for k, v in codes.items()))
