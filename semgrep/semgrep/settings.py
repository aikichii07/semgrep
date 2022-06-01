"""
Manages system settings for Semgrep

These can change the way Semgrep operates within the environment. They are distinct from config,
which describes which rules Semgrep should run.

To retrieve settings use `get_state().settings.get("key")`, to set them use `get_state().settings.set("key", "value").value = ...`.

If no settings have been configured on the system, DEFAULT_SETTINGS will be written.

If the process does not have permission to the settings path, a PermissionError will be raised;
callers should handle this gracefully.
"""
import os
from pathlib import Path
from typing import Any
from typing import cast
from typing import Mapping

from attr import define
from attr import field
from ruamel.yaml import YAML
from typing_extensions import Literal
from typing_extensions import TypedDict

from semgrep.constants import SEMGREP_SETTINGS_FILE
from semgrep.constants import SETTINGS_FILE
from semgrep.constants import USER_DATA_FOLDER
from semgrep.verbose_logging import getLogger

logger = getLogger(__name__)
yaml = YAML()
yaml.default_flow_style = False


class SettingsSchema(TypedDict, total=False):
    has_shown_metrics_notification: bool
    api_token: str


SettingsKeys = Literal["has_shown_metrics_notification", "api_token"]

DEFAULT_SETTINGS: SettingsSchema = {}


@define
class Settings:
    path: Path = field()
    _contents: SettingsSchema = field()

    @path.default
    def get_default_path(self) -> Path:
        """
        Uses {$XDG_CONFIG_HOME/semgrep || ~/.semgrep}/settings.yaml unless SEMGREP_SETTINGS_FILE is set
        """
        if SEMGREP_SETTINGS_FILE:
            return Path(SEMGREP_SETTINGS_FILE)

        return USER_DATA_FOLDER / SETTINGS_FILE

    @_contents.default
    def get_default_contents(self) -> SettingsSchema:
        """If file exists, read file. Otherwise use default"""
        # Must perform access check first in case we don't have permission to stat the path
        if not os.access(self.path, os.R_OK) or not self.path.is_file():
            return DEFAULT_SETTINGS.copy()

        with self.path.open() as fd:
            yaml_contents = yaml.load(fd)

        if not isinstance(yaml_contents, Mapping):
            logger.warning(
                f"Bad settings format; {self.path} will be overriden. Contents:\n{yaml_contents}"
            )
            return DEFAULT_SETTINGS.copy()

        return cast(SettingsSchema, yaml_contents)

    def save(self) -> None:
        try:
            if not self.path.parent.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)

            with self.path.open("w") as fd:
                yaml.dump(self._contents, fd)
        except PermissionError:
            logger.verbose("Could not write settings file at %s", self.path)

    def get(self, key: SettingsKeys, default: Any = None) -> Any:
        return self._contents.get(key, default)

    def set(self, key: SettingsKeys, value: Any) -> None:
        """
        Update and save this system's settings object

        :param value: The settings object
        """
        self._contents[key] = value
        self.save()

    def delete(self, key: SettingsKeys) -> None:
        """
        Deletes key KEY from settings file if it exists

        Noop otherwise
        """
        if key in self._contents:
            del self._contents[key]
            self.save()
