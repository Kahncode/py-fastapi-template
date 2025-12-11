import random
import string


def create_random_dict() -> dict:
    return {
        "key": "".join(random.choices(string.ascii_letters, k=8)),  # noqa: S311
        "value": random.randint(1, 100),  # noqa: S311
        "flag": random.choice([True, False]),  # noqa: S311
    }
