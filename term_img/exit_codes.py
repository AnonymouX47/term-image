"""Exit codes for fatal errors"""

codes = {
    0: "SUCCESS",
    1: "FAILURE",
    # Omit bash shell exit code 2
    3: "NO_VALID_SOURCE",
    4: "INVALID_SIZE",
    5: "CONFIG_ERROR",
    6: "INTERRUPTED",
}

globals().update(((v, k) for k, v in codes.items()))
