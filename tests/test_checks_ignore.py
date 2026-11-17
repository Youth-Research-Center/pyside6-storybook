"""``checks_ignore`` on ``story()``, ``StoryRegistry.story()``, ``Story`` and ``Story.variant()``."""

from types import MappingProxyType

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from pyside6_storybook import Story, StoryContext, StoryRegistry, story


def _build(ctx: StoryContext) -> QWidget:
    return QLabel("x")


def test_a_story_has_no_ignored_checks_by_default() -> None:
    assert dict(Story("A/b", _build).checks_ignore) == {}


def test_the_mapping_is_stored_read_only_and_copied() -> None:
    given = {"focus": "decorative"}
    registry = StoryRegistry()
    registered = registry.story("A/b", checks_ignore=given)(_build)

    given["name"] = "later"

    assert dict(registered.checks_ignore) == {"focus": "decorative"}
    assert isinstance(registered.checks_ignore, MappingProxyType)
    with pytest.raises(TypeError):
        registered.checks_ignore["name"] = "x"  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize("rule", ["snapshot", "Name", ""])
def test_an_unknown_rule_is_rejected_when_the_decorator_is_created(rule: str) -> None:
    with pytest.raises(ValueError, match=r"unknown rule .* expected one of 'name', 'focus', 'contrast'"):
        StoryRegistry().story("A/b", checks_ignore={rule: "why"})
    with pytest.raises(ValueError, match="unknown rule"):
        Story("A/b", _build, checks_ignore={rule: "why"})


@pytest.mark.parametrize("reason", ["", "   ", None, 3])
def test_an_empty_reason_is_rejected(reason: object) -> None:
    with pytest.raises(ValueError, match="needs a reason"):
        StoryRegistry().story("A/b", checks_ignore={"name": reason})  # ty: ignore[invalid-argument-type]


def test_something_that_is_not_a_mapping_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="checks_ignore"):
        Story("A/b", _build, checks_ignore=["name"])  # ty: ignore[invalid-argument-type]


def test_the_module_level_decorator_passes_checks_ignore(monkeypatch: pytest.MonkeyPatch) -> None:
    from pyside6_storybook import registry as registry_module

    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)

    @story("A/b", checks_ignore={"name": "icon only on purpose"})
    def build(ctx: StoryContext) -> QWidget:
        return QLabel("x")

    assert isolated.get("A/b").checks_ignore == {"name": "icon only on purpose"}


def test_a_variant_inherits_checks_ignore_unless_it_gives_its_own() -> None:
    registry = StoryRegistry()
    base = registry.story("A/b/Default", checks_ignore={"focus": "decorative"})(_build)

    inherited = base.variant("Same")
    replaced = base.variant("Other", checks_ignore={"name": "icon"})
    cleared = base.variant("None", checks_ignore={})

    assert dict(inherited.checks_ignore) == {"focus": "decorative"}
    assert dict(replaced.checks_ignore) == {"name": "icon"}
    assert dict(cleared.checks_ignore) == {}


def test_a_variant_validates_its_checks_ignore() -> None:
    registry = StoryRegistry()
    base = registry.story("A/b/Default")(_build)

    with pytest.raises(ValueError, match="unknown rule"):
        base.variant("Bad", checks_ignore={"nope": "x"})
    assert "A/b/Bad" not in registry
