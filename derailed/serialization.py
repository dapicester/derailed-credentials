from typing import Any

import yaml


def multiline_string_presenter(dumper, data):
    """Custom presenter multiline strings."""
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, multiline_string_presenter)

# to use with safe_dump:
yaml.representer.SafeRepresenter.add_representer(str, multiline_string_presenter)


def yaml_load(string: str) -> Any:
    """Load data from a YAML string."""
    return yaml.safe_load(string)


def yaml_dump(data: Any) -> str:
    """Dump data into a YAML string."""
    if not data:
        return ""
    return yaml.dump(
        data, allow_unicode=True, default_flow_style=False, sort_keys=False
    )
