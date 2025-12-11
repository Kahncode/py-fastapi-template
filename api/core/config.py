from shared.core.config import (
    Settings,
    override_settings_class,
)
from shared.core.config import (
    get_settings as get_base_settings,
)


# Settings class
class ApiSettings(Settings):
    # Add relevant API fields here
    pass


override_settings_class(ApiSettings)


def get_settings() -> ApiSettings:
    settings = get_base_settings()
    if not isinstance(settings, ApiSettings):
        msg = f"Expected ApiSettings, got {type(settings).__name__}"
        raise TypeError(msg)
    return settings
