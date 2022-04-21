"""Exit codes for fatal errors"""

from __future__ import annotations

codes = {
    0: "SUCCESS",
    1: "FAILURE",
    # Omit bash shell exit code 2
    3: "INVALID_ARG",
    4: "NO_VALID_SOURCE",
    5: "INVALID_SIZE",
    6: "CONFIG_ERROR",
    7: "INTERRUPTED",
}

globals().update(((v, k) for k, v in codes.items()))
