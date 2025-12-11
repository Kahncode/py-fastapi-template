from enum import Enum


# Enum for environment type, moved here for reuseability
class AppEnvironment(str, Enum):
    LOCAL = "local"
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"


def get_environment_suffix(environment: AppEnvironment) -> str:
    env_str = environment.value.lower()
    # Only add suffix for non-production
    return "" if environment == AppEnvironment.PRODUCTION else f"-{env_str}"
