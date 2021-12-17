"""Exit codes for fatal errors"""

codes = {
    0: "SUCCESS",
    1: "FAILURE",
    2: "NO_VALID_SOURCE",
    3: "INVALID_SIZE",
    4: "CONFIG_ERROR",
    5: "INTERRUPTED",
}

globals().update(((v, k) for k, v in codes.items()))
