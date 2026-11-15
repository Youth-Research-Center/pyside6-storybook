"""Form stories: several widgets composed into one component."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLineEdit, QPushButton, QWidget

from pyside6_storybook import BoolControl, StoryContext, TextControl, story


@story("Forms/Sign-in Form", controls=[TextControl("title", "Sign in"), BoolControl("show_remember", default=True)])
def sign_in_form(ctx: StoryContext) -> QWidget:
    """A composite: line edits, a check box and a button in a ``QGroupBox``. The form labels are the fields' buddies."""
    group = QGroupBox(ctx.args["title"])
    form = QFormLayout(group)
    email = QLineEdit(group)
    email.setPlaceholderText("name@example.com")
    form.addRow("&Email", email)
    password = QLineEdit(group)
    password.setEchoMode(QLineEdit.EchoMode.Password)
    form.addRow("&Password", password)
    if ctx.args["show_remember"]:
        form.addRow(QCheckBox("Remember me", group))
    form.addRow(QPushButton("Sign in", group))
    return group
