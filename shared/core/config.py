import importlib
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from packaging.version import Version
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from structlog import BoundLogger
from structlog.types import EventDict

from shared.core.app_environment import AppEnvironment
from shared.services.base_service import BaseService

# Load .env file if present as soon as this module is imported
load_dotenv()


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open() as f:
        return yaml.safe_load(f) or {}


def expand_env_vars(obj: Any) -> Any:  # noqa: ANN401
    if isinstance(obj, dict):
        return {k: expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [expand_env_vars(v) for v in obj]
    elif isinstance(obj, str):

        def replacer(m: re.Match) -> str:
            var_name = m.group(1)
            env_val = os.getenv(var_name)
            if env_val:
                return env_val
            # If not in env, treat var_name as a file path
            # (Useful for handling volume mounted secrets on GCP Cloud Run)
            if Path(var_name).is_file():
                try:
                    with Path(var_name).open("r", encoding="utf-8") as f:
                        return f.read().strip()
                except OSError:
                    return m.group(0)
            return m.group(0)

        return re.sub(r"\$\{([^\}]+)\}", replacer, obj)
    else:
        return obj


def resolve_symbol(symbol_str: str) -> type:
    module_name, class_name = symbol_str.rsplit(".", 1)
    module = importlib.import_module(module_name)
    symbol = getattr(module, class_name)
    if symbol is None:
        msg = f"Could not resolve symbol {symbol_str}"
        raise ValueError(msg)
    return symbol


# instanciates an object based on a string type and a dict for constructor parameters
def load_config_object[T](obj_dict: dict, cls_name: str, base_class: type[T]) -> T:
    # Find the class object by name in the current module's globals
    model_cls = resolve_symbol(cls_name)
    if not issubclass(model_cls, base_class):
        msg = f"{cls_name} is not a subclass of {base_class.__name__}"
        raise TypeError(msg)
    return model_cls(**obj_dict)


# loads an array of config objects, using cls_name_key as the key to resolve the type
def load_config_object_array[T](objects: list[dict], cls_name_key: str, base_class: type[T]) -> list[T]:
    if not objects:
        return []
    if not isinstance(objects, list):
        msg = "Expected a list of objects"
        raise TypeError(msg)
    serialized_objects = []
    for obj_dict in objects:
        serialized_object = load_config_object(obj_dict, obj_dict[cls_name_key], base_class)
        if serialized_object is None:
            msg = f"Could not load object from config {obj_dict}"
            raise ValueError(msg)
        serialized_objects.append(serialized_object)
    return serialized_objects


# Settings class
class Settings(BaseSettings):
    app_name: str | None = None
    app_version: Version | None = None
    app_environment: AppEnvironment = AppEnvironment.PRODUCTION  # Default to production for safety
    allowed_hosts: list[str] | None = None
    redirect_https: bool = False
    log_level: str = (
        "debug"  # Default to debug, however for any non-dev environment this will be overridden to "info" in the validator
    )
    log_processors: list[Callable[[BoundLogger, str, EventDict], EventDict]] | None = None
    services: list[BaseService] | None = None
    # Add more fields as needed

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False, frozen=True)

    @field_validator("app_version", mode="before")
    def parse_version(cls, v) -> Version | None:  # noqa: ANN001, N805
        return Version(v) if v else None

    @field_validator("log_processors", mode="before")
    def parse_log_processors(cls, v) -> list[Callable[[BoundLogger, str, EventDict], EventDict]]:  # noqa: ANN001, N805
        return [resolve_symbol(item) if isinstance(item, str) else item for item in v] if v else None

    @field_validator("services", mode="before")
    def parse_services(cls, v) -> list[object]:  # noqa: ANN001, N805
        return load_config_object_array(v, "type", object)

    @field_validator("log_level", mode="before")
    def set_log_level(cls, v, info) -> str:  # noqa: ANN001, N805
        env_type = info.data.get("app_environment", AppEnvironment.PRODUCTION)
        if env_type != AppEnvironment.DEVELOPMENT:
            return "info"
        return v if isinstance(v, str) else "info"

    def is_dev_environment(self) -> bool:
        return self.app_environment in (AppEnvironment.LOCAL, AppEnvironment.DEVELOPMENT)

    def get_service[T](self, base_class: type[T]) -> T | None:
        if not self.services:
            return None
        for service in self.services:
            if isinstance(service, base_class):
                return service
        return None


# Lazily initialized singleton config instance
_settings_instance: Settings | None = None
_settings_class: type[Settings] = Settings


def override_settings_class(new_class: type[Settings]) -> None:
    global _settings_class  # noqa: PLW0603
    if _settings_class != Settings:
        msg = "Settings class can only be overridden once and only if it is the default Settings class"
        raise RuntimeError(msg)
    if _settings_instance:
        msg = "Settings instance has already been created, cannot override class"
        raise RuntimeError(msg)
    _settings_class = new_class


def get_settings() -> Settings:
    global _settings_instance  # noqa: PLW0603
    if _settings_instance is None:
        yaml_path = os.getenv("CONFIG_YAML_PATH")
        if not yaml_path:
            msg = "CONFIG_YAML_PATH environment variable is not set. Cannot load YAML config."
            raise RuntimeError(msg)

        # Using print here to avoid circular import with shared.core.logging
        print("Loading configuration from: ", yaml_path)  # noqa: T201

        # Pydantic will merge env vars (top level only), .env, and yaml_config
        # We are not using pydancic's built-in yaml support because we want to
        # expand env vars in a more advanced way in the yaml file first
        # See SettingsConfigDict for more details

        yaml_config = load_yaml_config(yaml_path)
        yaml_config = expand_env_vars(yaml_config)

        _settings_instance = _settings_class(**yaml_config)
    return _settings_instance
