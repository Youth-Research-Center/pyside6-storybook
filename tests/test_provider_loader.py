import sys
from pathlib import Path

import pytest
from story_files import write

from pyside6_storybook import StoryRegistry
from pyside6_storybook.themes.provider_loader import PROTOCOL_METHODS, ThemeProviderError, load_theme_provider

_METHODS = """
    def theme_names(self):
        return ("Paper", "Ink")

    def current_theme(self):
        return "Paper"

    def activate(self, app):
        pass

    def set_theme(self, name):
        pass

    def on_changed(self, callback):
        pass

    def deactivate(self):
        pass
"""


@pytest.fixture
def modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry) -> Path:
    """A folder on ``sys.path`` for provider modules; ``stories`` restores ``sys.path`` and ``sys.modules``."""
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path


def _provider_module(root: Path, name: str, body: str) -> None:
    write(root, f"{name}.py", f"class Provider:\n{_METHODS}\n\n{body}")


def test_an_instance_is_used_as_it_is(modules: Path) -> None:
    _provider_module(modules, "instance_theming", "provider = Provider()\n")

    loaded = load_theme_provider("instance_theming:provider")

    assert loaded.provider is sys.modules["instance_theming"].provider
    assert loaded.provider.theme_names() == ("Paper", "Ink")


def test_a_factory_function_is_called_once(modules: Path) -> None:
    _provider_module(modules, "factory_theming", "calls = []\n\ndef make_provider():\n    calls.append(1)\n    return Provider()\n")

    loaded = load_theme_provider("factory_theming:make_provider")

    assert sys.modules["factory_theming"].calls == [1]
    assert loaded.provider.current_theme() == "Paper"


def test_a_class_is_instantiated(modules: Path) -> None:
    _provider_module(modules, "class_theming", "")

    loaded = load_theme_provider("class_theming:Provider")

    assert type(loaded.provider) is sys.modules["class_theming"].Provider


def test_a_callable_instance_is_not_called(modules: Path) -> None:
    body = "class Callable(Provider):\n    def __call__(self):\n        raise AssertionError('called')\n\nprovider = Callable()\n"
    _provider_module(modules, "callable_theming", body)

    assert load_theme_provider("callable_theming:provider").provider is sys.modules["callable_theming"].provider


def test_a_dotted_attribute_is_resolved(modules: Path) -> None:
    _provider_module(modules, "dotted_theming", "class Holder:\n    provider = Provider()\n")

    loaded = load_theme_provider("dotted_theming:Holder.provider")

    assert loaded.provider is sys.modules["dotted_theming"].Holder.provider


def test_the_modules_the_import_and_the_call_added_are_returned(modules: Path) -> None:
    write(modules, "theming_app/__init__.py", "")
    write(modules, "theming_app/manager.py", "NAME = 'manager'\n")
    write(modules, "theming_app/lazy.py", "NAME = 'lazy'\n")
    source = f"from theming_app import manager\n\nclass Provider:\n{_METHODS}\n\ndef make():\n    import theming_app.lazy\n    return Provider()\n"
    write(modules, "theming_app/theming.py", source)

    loaded = load_theme_provider("theming_app.theming:make")

    assert {"theming_app", "theming_app.manager", "theming_app.theming", "theming_app.lazy"} <= set(loaded.modules)


def test_a_module_that_was_already_imported_is_not_recorded(modules: Path) -> None:
    _provider_module(modules, "early_theming", "provider = Provider()\n")
    __import__("early_theming")

    assert "early_theming" not in load_theme_provider("early_theming:provider").modules


def test_an_instance_with_a_non_callable_method_is_rejected(modules: Path) -> None:
    _provider_module(modules, "attribute_theming", 'class Static(Provider):\n    theme_names = ("Paper", "Ink")\n\nprovider = Static()\n')

    with pytest.raises(ThemeProviderError, match="attribute_theming:provider") as error_info:
        load_theme_provider("attribute_theming:provider")

    assert "theme_names" in str(error_info.value)


def test_a_factory_result_with_missing_methods_names_them(modules: Path) -> None:
    write(modules, "partial_theming.py", "class Partial:\n    def theme_names(self):\n        return ('A',)\n\ndef make():\n    return Partial()\n")

    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider("partial_theming:make")

    message = str(error_info.value)
    assert "partial_theming:make" in message
    assert all(name in message for name in PROTOCOL_METHODS if name != "theme_names")
    assert "theme_names" not in message.split("missing or not callable:")[1]


def test_a_plain_object_is_not_a_provider(modules: Path) -> None:
    write(modules, "plain_theming.py", "provider = 3\n")

    with pytest.raises(ThemeProviderError, match="plain_theming:provider"):
        load_theme_provider("plain_theming:provider")


@pytest.mark.parametrize("spec", ["", "nocolon", ":attribute", "module:", "a:b:c"])
def test_a_malformed_spec_names_the_expected_form(spec: str) -> None:
    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider(spec)

    assert f"{spec!r}" in str(error_info.value)
    assert "expected 'module:attribute'" in str(error_info.value)


def test_a_missing_module_names_the_spec_and_the_module(modules: Path) -> None:
    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider("no_such_theming:provider")

    message = str(error_info.value)
    assert "no_such_theming:provider" in message
    assert "ModuleNotFoundError" in message


def test_a_module_that_raises_on_import_names_the_exception(modules: Path) -> None:
    write(modules, "raising_theming.py", "raise RuntimeError('broken at import')\n")

    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider("raising_theming:provider")

    message = str(error_info.value)
    assert "raising_theming:provider" in message
    assert "broken at import" in message
    assert "raising_theming" not in sys.modules


def test_a_missing_attribute_names_the_attribute_and_the_module(modules: Path) -> None:
    _provider_module(modules, "empty_theming", "")

    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider("empty_theming:nothing.here")

    message = str(error_info.value)
    assert "empty_theming:nothing.here" in message
    assert "'nothing.here'" in message
    assert "'empty_theming'" in message


def test_a_factory_that_raises_names_the_callable_and_the_exception(modules: Path) -> None:
    write(modules, "factory_raising_theming.py", "def make():\n    raise RuntimeError('factory failed')\n")

    with pytest.raises(ThemeProviderError) as error_info:
        load_theme_provider("factory_raising_theming:make")

    message = str(error_info.value)
    assert "factory_raising_theming:make" in message
    assert "'make'" in message
    assert "factory failed" in message


def test_a_class_whose_constructor_raises_is_reported(modules: Path) -> None:
    write(modules, "constructor_theming.py", "class Provider:\n    def __init__(self):\n        raise ValueError('no constructor')\n")

    with pytest.raises(ThemeProviderError, match="no constructor"):
        load_theme_provider("constructor_theming:Provider")
