GIGABYTE: int = 1024 * 1024 * 1024
MEGABYTE: int = 1024 * 1024
KILOBYTE: int = 1024


def format_byte_size(byte_size: int) -> str:
    if byte_size >= GIGABYTE:
        return f"{byte_size / GIGABYTE:.2f} GB"
    elif byte_size >= MEGABYTE:
        return f"{byte_size / MEGABYTE:.2f} MB"
    elif byte_size >= KILOBYTE:
        return f"{byte_size / KILOBYTE:.2f} KB"
    else:
        return f"{byte_size} bytes"
