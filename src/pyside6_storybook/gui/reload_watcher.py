"""``ReloadWatcher``: watches the project's files and runs a reload when one changes."""

from __future__ import annotations

import logging

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from pyside6_storybook.discovery.reload import ReloadSession

DEBOUNCE_MS = 300


class ReloadWatcher(QObject):
    """Runs ``ReloadSession.reload`` after the files of the project change, and emits the result.

    It watches the project's modules and every story source (also one that fails to import), and every folder below each folder
    target, because a folder watch is not recursive. A change to a folder counts only when the set of story files below the folder
    targets changed, so an editor's swap and backup files do not reload. Changes are collected for 300 ms, so a burst of events runs one
    reload, and a reload never starts while another runs. After every event and every reload the watched paths are collected again:
    editors that save by renaming drop the watch on the file, and a reload may import files for the first time.

    Signals:
        reloaded: Emitted with the ``ReloadResult`` after each reload, accepted or not.
    """

    reloaded = Signal(object)

    def __init__(self, session: ReloadSession, parent: QObject | None = None, *, debounce_ms: int = DEBOUNCE_MS) -> None:
        """Create the watcher and start watching.

        Args:
            session: The reload session whose files are watched and whose ``reload`` is run.
            parent: The owning object.
            debounce_ms: How long to wait after the last change before reloading.
        """
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = session
        self._running = False
        self._again = False
        self._story_files = session.story_file_set()
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._run)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._collect()

    def watched_paths(self) -> list[str]:
        """Return the files and folders being watched."""
        return [*self._watcher.files(), *self._watcher.directories()]

    def trigger_now(self) -> None:
        """Run a reload now, without waiting for the debounce; for tests."""
        self._timer.stop()
        self._run()

    def _on_file_changed(self, _path: str) -> None:
        self._collect()
        self._schedule()

    def _on_directory_changed(self, _path: str) -> None:
        self._collect()
        story_files = self._session.story_file_set()
        if story_files != self._story_files:
            self._story_files = story_files
            self._schedule()

    def _schedule(self) -> None:
        if self._running:
            self._again = True
        else:
            self._timer.start()

    def _run(self) -> None:
        if self._running:
            self._again = True
            return
        self._running = True
        try:
            self._collect()
            result = self._session.reload()
        except Exception:
            self._logger.exception("Reloading the stories failed")
            return
        finally:
            self._running = False
        self._story_files = self._session.story_file_set()
        self._collect()
        self.reloaded.emit(result)
        if self._again:
            self._again = False
            self._timer.start()

    def _collect(self) -> None:
        """Watch every file and folder that should be watched and is not, and drop the ones that are gone."""
        files = {str(path) for path in self._session.watched_files()}
        folders = {str(path) for path in self._session.watched_folders()}
        watched = set(self._watcher.files()) | set(self._watcher.directories())
        stale = [path for path in watched if path not in files and path not in folders]
        if stale:
            self._watcher.removePaths(stale)
        missing = sorted((files | folders) - watched)
        if missing:
            failed = self._watcher.addPaths(missing)
            if failed:
                self._logger.debug("Could not watch %s", ", ".join(failed))


__all__ = ["DEBOUNCE_MS", "ReloadWatcher"]
