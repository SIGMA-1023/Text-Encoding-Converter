from __future__ import annotations

import ctypes
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "UST Text Encoding Converter"

DEFAULT_EXTENSIONS = {
    ".ust",
    ".txt",
    ".ini",
    ".cfg",
    ".csv",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".fx",
    ".shader",
    ".hlsl",
    ".cg",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".lua",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".md",
}

ENCODINGS_TO_TRY = ("utf-8", "utf-8-sig", "cp932", "shift_jis")
SUCCESS_MARK = "OK"
SKIP_MARK = "SKIP"
FAIL_MARK = "FAIL"


@dataclass(frozen=True)
class SourceFile:
    """A file selected by the user and the base path used for output mirroring."""

    path: Path
    base_dir: Path


@dataclass(frozen=True)
class FileTimes:
    """Windows and POSIX timestamp fields needed to restore file metadata."""

    created_ns: int
    modified_ns: int
    accessed_ns: int


@dataclass(frozen=True)
class ConversionOptions:
    """All mutable GUI options copied before the worker thread starts."""

    overwrite: bool
    output_dir: Path | None
    auto_backup: bool
    keep_modified_time: bool
    keep_created_time: bool
    keep_newlines: bool
    auto_detect_encoding: bool
    recursive: bool


@dataclass(frozen=True)
class ConversionResult:
    """Result for one file."""

    status: str
    source: Path
    target: Path | None
    message: str


def normalize_extensions(raw_text: str) -> set[str]:
    """Parse the editable extension list while keeping future customization simple."""

    extensions: set[str] = set()
    for token in raw_text.replace(",", "\n").replace(";", "\n").splitlines():
        ext = token.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        extensions.add(ext)
    return extensions


def discover_files(paths: Iterable[Path], extensions: set[str], recursive: bool) -> list[SourceFile]:
    """Expand dropped files and folders into supported text files."""

    found: dict[Path, SourceFile] = {}
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_file():
            if path.suffix.lower() in extensions:
                found[path] = SourceFile(path=path, base_dir=path.parent)
            continue

        if not path.is_dir():
            continue

        iterator = path.rglob("*") if recursive else path.glob("*")
        base_dir = path.parent
        for child in iterator:
            if child.is_file() and child.suffix.lower() in extensions:
                found[child.resolve()] = SourceFile(path=child.resolve(), base_dir=base_dir)

    return sorted(found.values(), key=lambda item: str(item.path).lower())


def get_file_times(path: Path) -> FileTimes:
    """Capture access, modification, and Windows creation time before writing."""

    stat = path.stat()
    return FileTimes(
        created_ns=getattr(stat, "st_birthtime_ns", stat.st_ctime_ns),
        modified_ns=stat.st_mtime_ns,
        accessed_ns=stat.st_atime_ns,
    )


def restore_file_times(path: Path, times: FileTimes, keep_modified: bool, keep_created: bool) -> None:
    """Restore requested timestamps. Creation time restoration uses Win32 APIs."""

    if keep_modified:
        os.utime(path, ns=(times.accessed_ns, times.modified_ns))
    if keep_created and os.name == "nt":
        set_windows_creation_time(path, times.created_ns, times.accessed_ns, times.modified_ns)


def ns_to_filetime(ns: int) -> int:
    """Convert Unix nanoseconds to a Windows FILETIME integer."""

    return int(ns / 100) + 116444736000000000


def set_windows_creation_time(path: Path, created_ns: int, accessed_ns: int, modified_ns: int) -> None:
    """Restore Windows creation time without requiring pywin32."""

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        str(path),
        0x0100,  # FILE_WRITE_ATTRIBUTES
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,  # OPEN_EXISTING
        0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
        None,
    )
    if handle == -1:
        raise OSError("Unable to open file for timestamp restoration.")

    try:
        ctime = ctypes.c_longlong(ns_to_filetime(created_ns))
        atime = ctypes.c_longlong(ns_to_filetime(accessed_ns))
        mtime = ctypes.c_longlong(ns_to_filetime(modified_ns))
        ok = kernel32.SetFileTime(
            handle,
            ctypes.byref(ctime),
            ctypes.byref(atime),
            ctypes.byref(mtime),
        )
        if not ok:
            raise OSError("Unable to restore Windows creation time.")
    finally:
        kernel32.CloseHandle(handle)


def read_text_without_changing_newlines(path: Path, encoding: str, keep_newlines: bool) -> str:
    """Read text exactly as decoded; newline='' prevents Python newline normalization."""

    newline = "" if keep_newlines else None
    with path.open("r", encoding=encoding, newline=newline) as file:
        return file.read()


def write_utf8_without_bom(path: Path, text: str, keep_newlines: bool) -> None:
    """Write UTF-8 without BOM. newline='' keeps CRLF/LF/CR sequences unchanged."""

    path.parent.mkdir(parents=True, exist_ok=True)
    newline = "" if keep_newlines else None
    with path.open("w", encoding="utf-8", newline=newline) as file:
        file.write(text)


def detect_encoding(path: Path, keep_newlines: bool, auto_detect: bool) -> tuple[str | None, str | None]:
    """Try supported encodings in order, while treating UTF-8 BOM as removable."""

    has_utf8_bom = path.read_bytes().startswith(b"\xef\xbb\xbf")
    candidates = ENCODINGS_TO_TRY if auto_detect else ("cp932",)
    for encoding in candidates:
        if has_utf8_bom and encoding == "utf-8":
            continue
        try:
            text = read_text_without_changing_newlines(path, encoding, keep_newlines)
            return encoding, text
        except UnicodeDecodeError:
            continue
    return None, None


def unique_backup_path(path: Path) -> Path:
    """Create test.ust.bak, test.ust.bak1, test.ust.bak2, etc. without overwriting."""

    first = Path(f"{path}.bak")
    if not first.exists():
        return first
    index = 1
    while True:
        candidate = Path(f"{path}.bak{index}")
        if not candidate.exists():
            return candidate
        index += 1


def make_backup(path: Path) -> Path:
    """Copy the original bytes and metadata before converting."""

    backup_path = unique_backup_path(path)
    shutil.copy2(path, backup_path)
    if os.name == "nt":
        try:
            times = get_file_times(path)
            restore_file_times(backup_path, times, keep_modified=True, keep_created=True)
        except OSError:
            pass
    return backup_path


def target_path_for(source: SourceFile, options: ConversionOptions) -> Path:
    """Resolve overwrite or mirrored output-directory target."""

    if options.overwrite:
        return source.path
    if options.output_dir is None:
        raise ValueError("Output directory is required.")
    relative = source.path.relative_to(source.base_dir)
    return options.output_dir / relative


def convert_one_file(source: SourceFile, options: ConversionOptions) -> ConversionResult:
    """Convert a single file, guaranteeing that failures do not escape the worker."""

    try:
        original_times = get_file_times(source.path)
        encoding, text = detect_encoding(
            source.path,
            keep_newlines=options.keep_newlines,
            auto_detect=options.auto_detect_encoding,
        )
        if encoding is None or text is None:
            return ConversionResult(FAIL_MARK, source.path, None, "\u5931\u8d25\uff08\u672a\u77e5\u7f16\u7801\uff09")

        target = target_path_for(source, options)
        if encoding == "utf-8":
            if options.overwrite:
                return ConversionResult(SKIP_MARK, source.path, target, "\u8df3\u8fc7\uff08\u5df2\u7ecf\u662f UTF-8\uff09")
            write_utf8_without_bom(target, text, options.keep_newlines)
            restore_file_times(target, original_times, options.keep_modified_time, options.keep_created_time)
            return ConversionResult(SKIP_MARK, source.path, target, "\u8df3\u8fc7\uff08\u6e90\u6587\u4ef6\u5df2\u7ecf\u662f UTF-8\uff0c\u5df2\u590d\u5236\u5230\u8f93\u51fa\u76ee\u5f55\uff09")

        if options.overwrite and options.auto_backup:
            make_backup(source.path)

        write_utf8_without_bom(target, text, options.keep_newlines)
        restore_file_times(target, original_times, options.keep_modified_time, options.keep_created_time)
        return ConversionResult(SUCCESS_MARK, source.path, target, "\u221a \u6210\u529f")
    except Exception as exc:  # noqa: BLE001 - each file must fail independently.
        return ConversionResult(FAIL_MARK, source.path, None, f"\u5931\u8d25\uff08{exc}\uff09")


class ConversionWorker(QThread):
    """Background converter so large batches never freeze the GUI."""

    started_message = Signal(str)
    current_file = Signal(str)
    file_done = Signal(ConversionResult, int, int)
    finished_summary = Signal(int, int, int)

    def __init__(self, files: list[SourceFile], options: ConversionOptions) -> None:
        super().__init__()
        self.files = files
        self.options = options
        self.success_count = 0
        self.skip_count = 0
        self.fail_count = 0

    def run(self) -> None:
        total = len(self.files)
        self.started_message.emit("\u5f00\u59cb\u8f6c\u6362...")
        for index, source in enumerate(self.files, start=1):
            self.current_file.emit(f"\u6b63\u5728\u5904\u7406\uff1a{source.path.name}")
            result = convert_one_file(source, self.options)
            if result.status == SUCCESS_MARK:
                self.success_count += 1
            elif result.status == SKIP_MARK:
                self.skip_count += 1
            else:
                self.fail_count += 1
            self.file_done.emit(result, index, total)
        self.started_message.emit("\u5b8c\u6210\u3002")
        self.finished_summary.emit(self.success_count, self.skip_count, self.fail_count)


class DropArea(QFrame):
    """Drag-and-drop target for files and folders."""

    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        layout = QVBoxLayout(self)
        label = QLabel("\u5c06\u6587\u4ef6\u6216\u6587\u4ef6\u5939\u62d6\u5230\u8fd9\u91cc")
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("dropText")
        layout.addWidget(label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    """Main GUI window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 840)
        self.sources: list[SourceFile] = []
        self.worker: ConversionWorker | None = None
        self.build_ui()
        self.apply_style()

    def build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setSpacing(14)
        root.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Text Encoding Converter")
        title.setObjectName("title")
        root.addWidget(title)

        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.add_paths)
        root.addWidget(self.drop_area)

        files_box = QGroupBox("\u5f85\u5904\u7406\u6587\u4ef6")
        files_layout = QVBoxLayout(files_box)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        files_layout.addWidget(self.file_list)

        file_buttons = QHBoxLayout()
        add_files_button = QPushButton("\u6dfb\u52a0\u6587\u4ef6")
        add_files_button.clicked.connect(self.choose_files)
        add_folder_button = QPushButton("\u6dfb\u52a0\u6587\u4ef6\u5939")
        add_folder_button.clicked.connect(self.choose_folder)
        remove_button = QPushButton("\u79fb\u9664\u9009\u4e2d")
        remove_button.clicked.connect(self.remove_selected_files)
        clear_button = QPushButton("\u6e05\u7a7a")
        clear_button.clicked.connect(self.clear_files)
        file_buttons.addWidget(add_files_button)
        file_buttons.addWidget(add_folder_button)
        file_buttons.addWidget(remove_button)
        file_buttons.addWidget(clear_button)
        file_buttons.addStretch()
        files_layout.addLayout(file_buttons)
        root.addWidget(files_box, stretch=2)

        output_box = QGroupBox("\u8f93\u51fa\u65b9\u5f0f")
        output_layout = QGridLayout(output_box)
        self.overwrite_radio = QRadioButton("\u8986\u76d6\u539f\u6587\u4ef6")
        self.output_dir_radio = QRadioButton("\u8f93\u51fa\u5230\u6307\u5b9a\u76ee\u5f55")
        self.overwrite_radio.setChecked(True)
        output_group = QButtonGroup(self)
        output_group.addButton(self.overwrite_radio)
        output_group.addButton(self.output_dir_radio)
        output_group.buttonClicked.connect(self.update_output_controls)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("\u9009\u62e9\u8f93\u51fa\u76ee\u5f55")
        self.output_dir_edit.setEnabled(False)
        browse_button = QPushButton("\u6d4f\u89c8")
        browse_button.clicked.connect(self.choose_output_dir)
        self.output_browse_button = browse_button
        self.output_browse_button.setEnabled(False)
        output_layout.addWidget(self.overwrite_radio, 0, 0, 1, 2)
        output_layout.addWidget(self.output_dir_radio, 1, 0, 1, 2)
        output_layout.addWidget(QLabel("\u8f93\u51fa\u76ee\u5f55\uff1a"), 2, 0)
        output_layout.addWidget(self.output_dir_edit, 2, 1)
        output_layout.addWidget(self.output_browse_button, 2, 2)
        root.addWidget(output_box)

        options_box = QGroupBox("\u9009\u9879")
        options_layout = QGridLayout(options_box)
        self.backup_check = QCheckBox("\u81ea\u52a8\u5907\u4efd\u539f\u6587\u4ef6")
        self.keep_mtime_check = QCheckBox("\u4fdd\u7559\u6587\u4ef6\u4fee\u6539\u65f6\u95f4")
        self.keep_ctime_check = QCheckBox("\u4fdd\u7559\u6587\u4ef6\u521b\u5efa\u65f6\u95f4\uff08Windows\uff09")
        self.keep_newlines_check = QCheckBox("\u4fdd\u7559\u539f\u59cb\u6362\u884c\u7b26")
        self.detect_check = QCheckBox("\u81ea\u52a8\u8bc6\u522b\u7f16\u7801")
        self.recursive_check = QCheckBox("\u9012\u5f52\u5904\u7406\u5b50\u6587\u4ef6\u5939")
        for checkbox in (
            self.backup_check,
            self.keep_mtime_check,
            self.keep_ctime_check,
            self.keep_newlines_check,
            self.detect_check,
            self.recursive_check,
        ):
            checkbox.setChecked(True)
        self.recursive_check.stateChanged.connect(self.refresh_sources_from_existing_roots)
        options_layout.addWidget(self.backup_check, 0, 0)
        options_layout.addWidget(self.keep_mtime_check, 0, 1)
        options_layout.addWidget(self.keep_ctime_check, 1, 0)
        options_layout.addWidget(self.keep_newlines_check, 1, 1)
        options_layout.addWidget(self.detect_check, 2, 0)
        options_layout.addWidget(self.recursive_check, 2, 1)
        root.addWidget(options_box)

        ext_box = QGroupBox("\u6269\u5c55\u540d\u5217\u8868")
        ext_layout = QVBoxLayout(ext_box)
        self.extensions_edit = QTextEdit()
        self.extensions_edit.setFixedHeight(82)
        self.extensions_edit.setPlainText("\n".join(sorted(DEFAULT_EXTENSIONS)))
        self.extensions_edit.textChanged.connect(self.refresh_sources_from_existing_roots)
        ext_layout.addWidget(self.extensions_edit)
        root.addWidget(ext_box)

        start_layout = QHBoxLayout()
        self.start_button = QPushButton("\u5f00\u59cb\u8f6c\u6362")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_conversion)
        start_layout.addStretch()
        start_layout.addWidget(self.start_button)
        root.addLayout(start_layout)

        progress_box = QGroupBox("\u8fdb\u5ea6")
        progress_layout = QHBoxLayout(progress_box)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat("%p%")
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setMinimumWidth(70)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        root.addWidget(progress_box)

        log_box = QGroupBox("\u65e5\u5fd7")
        log_layout = QVBoxLayout(log_box)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_edit)
        log_buttons = QHBoxLayout()
        copy_log_button = QPushButton("\u590d\u5236\u65e5\u5fd7")
        copy_log_button.clicked.connect(self.copy_log)
        save_log_button = QPushButton("\u4fdd\u5b58\u65e5\u5fd7")
        save_log_button.clicked.connect(self.save_log)
        log_buttons.addWidget(copy_log_button)
        log_buttons.addWidget(save_log_button)
        log_buttons.addStretch()
        log_layout.addLayout(log_buttons)
        root.addWidget(log_box, stretch=2)

        self.summary_label = QLabel("\u6210\u529f\uff1a0    \u8df3\u8fc7\uff1a0    \u5931\u8d25\uff1a0")
        self.summary_label.setObjectName("summary")
        root.addWidget(self.summary_label)

        self.setCentralWidget(central)

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 14px;
                color: #202124;
                background: #f7f8fb;
            }
            QGroupBox {
                border: 1px solid #d9dde7;
                border-radius: 8px;
                margin-top: 10px;
                padding: 14px 12px 12px 12px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #3b3f4a;
                background: #ffffff;
                font-weight: 600;
            }
            #title {
                font-size: 24px;
                font-weight: 650;
                color: #1f2937;
            }
            #dropArea {
                min-height: 92px;
                border: 2px dashed #8aa4d6;
                border-radius: 8px;
                background: #eef4ff;
            }
            #dropText {
                font-size: 18px;
                color: #355f9f;
                background: transparent;
            }
            QListWidget, QLineEdit, QTextEdit, QPlainTextEdit {
                border: 1px solid #cfd6e4;
                border-radius: 6px;
                background: #ffffff;
                padding: 7px;
                selection-background-color: #dbeafe;
            }
            QPushButton {
                border: 1px solid #c9d2e3;
                border-radius: 6px;
                padding: 8px 16px;
                background: #ffffff;
            }
            QPushButton:hover {
                background: #f0f5ff;
            }
            QPushButton:disabled {
                color: #8a93a3;
                background: #eef0f4;
            }
            #primaryButton {
                color: #ffffff;
                background: #2563eb;
                border-color: #2563eb;
                font-weight: 650;
                min-width: 150px;
            }
            #primaryButton:hover {
                background: #1d4ed8;
            }
            QProgressBar {
                border: 1px solid #cfd6e4;
                border-radius: 6px;
                text-align: center;
                background: #edf1f7;
                height: 24px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: #22c55e;
            }
            #summary {
                font-weight: 650;
                color: #1f2937;
                padding: 4px;
            }
            """
        )

    def selected_extensions(self) -> set[str]:
        extensions = normalize_extensions(self.extensions_edit.toPlainText())
        return extensions or set(DEFAULT_EXTENSIONS)

    def add_paths(self, paths: list[Path]) -> None:
        discovered = discover_files(paths, self.selected_extensions(), self.recursive_check.isChecked())
        known = {source.path for source in self.sources}
        self.sources.extend(source for source in discovered if source.path not in known)
        self.rebuild_file_list()

    def refresh_sources_from_existing_roots(self) -> None:
        # Existing individual entries are filtered by the current extension list.
        extensions = self.selected_extensions()
        self.sources = [source for source in self.sources if source.path.exists() and source.path.suffix.lower() in extensions]
        self.rebuild_file_list()

    def rebuild_file_list(self) -> None:
        self.file_list.clear()
        for source in self.sources:
            item = QListWidgetItem(str(source.path))
            item.setCheckState(Qt.Checked)
            self.file_list.addItem(item)

    def checked_sources(self) -> list[SourceFile]:
        checked_paths = {
            Path(self.file_list.item(index).text())
            for index in range(self.file_list.count())
            if self.file_list.item(index).checkState() == Qt.Checked
        }
        return [source for source in self.sources if source.path in checked_paths]

    def choose_files(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(self, "\u9009\u62e9\u6587\u4ef6")
        if filenames:
            self.add_paths([Path(name) for name in filenames])

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "\u9009\u62e9\u6587\u4ef6\u5939")
        if folder:
            self.add_paths([Path(folder)])

    def choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "\u9009\u62e9\u8f93\u51fa\u76ee\u5f55")
        if folder:
            self.output_dir_edit.setText(folder)

    def update_output_controls(self, *args: object) -> None:
        enabled = self.output_dir_radio.isChecked()
        self.output_dir_edit.setEnabled(enabled)
        self.output_browse_button.setEnabled(enabled)

    def remove_selected_files(self) -> None:
        selected = {Path(item.text()) for item in self.file_list.selectedItems()}
        self.sources = [source for source in self.sources if source.path not in selected]
        self.rebuild_file_list()

    def clear_files(self) -> None:
        self.sources.clear()
        self.rebuild_file_list()

    def build_options(self) -> ConversionOptions | None:
        overwrite = self.overwrite_radio.isChecked()
        output_dir = Path(self.output_dir_edit.text()).resolve() if self.output_dir_edit.text().strip() else None
        if not overwrite and output_dir is None:
            QMessageBox.warning(self, APP_NAME, "\u8bf7\u9009\u62e9\u8f93\u51fa\u76ee\u5f55\u3002")
            return None
        return ConversionOptions(
            overwrite=overwrite,
            output_dir=output_dir,
            auto_backup=self.backup_check.isChecked(),
            keep_modified_time=self.keep_mtime_check.isChecked(),
            keep_created_time=self.keep_ctime_check.isChecked(),
            keep_newlines=self.keep_newlines_check.isChecked(),
            auto_detect_encoding=self.detect_check.isChecked(),
            recursive=self.recursive_check.isChecked(),
        )

    def start_conversion(self) -> None:
        sources = self.checked_sources()
        if not sources:
            QMessageBox.information(self, APP_NAME, "\u8bf7\u5148\u6dfb\u52a0\u5e76\u52fe\u9009\u5f85\u5904\u7406\u6587\u4ef6\u3002")
            return
        options = self.build_options()
        if options is None:
            return

        self.log_edit.clear()
        self.summary_label.setText("\u6210\u529f\uff1a0    \u8df3\u8fc7\uff1a0    \u5931\u8d25\uff1a0")
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0 / {len(sources)}")
        self.start_button.setEnabled(False)

        self.worker = ConversionWorker(sources, options)
        self.worker.started_message.connect(self.append_log)
        self.worker.current_file.connect(self.append_log)
        self.worker.file_done.connect(self.on_file_done)
        self.worker.finished_summary.connect(self.on_finished)
        self.worker.start()

    def on_file_done(self, result: ConversionResult, done: int, total: int) -> None:
        percent = int(done * 100 / total) if total else 0
        target_info = f" -> {result.target}" if result.target and result.target != result.source else ""
        self.append_log(f"{result.source.name}{target_info}")
        self.append_log(result.message)
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{done} / {total}")

    def on_finished(self, success: int, skipped: int, failed: int) -> None:
        self.summary_label.setText(f"\u6210\u529f\uff1a{success}    \u8df3\u8fc7\uff1a{skipped}    \u5931\u8d25\uff1a{failed}")
        self.append_log("")
        self.append_log(f"\u6210\u529f\uff1a{success}")
        self.append_log(f"\u8df3\u8fc7\uff1a{skipped}")
        self.append_log(f"\u5931\u8d25\uff1a{failed}")
        self.start_button.setEnabled(True)
        self.worker = None

    def append_log(self, message: str) -> None:
        self.log_edit.appendPlainText(message)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def copy_log(self) -> None:
        QApplication.clipboard().setText(self.log_edit.toPlainText())

    def save_log(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "\u4fdd\u5b58\u65e5\u5fd7", "conversion-log.txt", "Text Files (*.txt)")
        if not filename:
            return
        Path(filename).write_text(self.log_edit.toPlainText(), encoding="utf-8", newline="")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, APP_NAME, "\u8f6c\u6362\u4ecd\u5728\u8fdb\u884c\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210\u3002")
            event.ignore()
            return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
