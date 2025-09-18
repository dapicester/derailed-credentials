from textwrap import dedent

from derailed.serialization import yaml_dump, yaml_load


def test_string():
    input_string = dedent("""
        key1: This is a regular string.
        key2: |-
          This is a multi-line
          string that will be
          dumped as a literal block scalar.
        key3: Another regular string.
    """).lstrip()

    data = yaml_load(input_string)
    assert data == {
        "key1": "This is a regular string.",
        "key2": "This is a multi-line\nstring that will be\ndumped as a literal block scalar.",
        "key3": "Another regular string.",
    }

    dumped_string = yaml_dump(data)
    assert dumped_string == input_string
