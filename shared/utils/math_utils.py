import math
import sys


def sanitize_float(value: float, nan: float = 0.0, posinf: float | None = None, neginf: float | None = None) -> float:
    """
    Replace NaN and Inf float values, similar to torch.nan_to_num behavior.

    Args:
        value: The float value to sanitize
        nan: Value to replace NaN with (default: 0.0)
        posinf: Value to replace +Inf with (default: largest finite float)
        neginf: Value to replace -Inf with (default: smallest finite float)

    Returns:
        The sanitized float value

    """
    if math.isnan(value):
        return nan
    if math.isinf(value):
        if value > 0:
            return posinf if posinf is not None else sys.float_info.max
        else:
            return neginf if neginf is not None else -sys.float_info.max
    return value
