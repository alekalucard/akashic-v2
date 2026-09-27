"""
KnowledgeDigestionFairy GUI - Knowledge Digestion Control Panel

Provides a GUI for controlling what gets digested into the Association Cortex.
Like the old ScrapeFairy GUI but focused on digestion/integration instead of raw scraping.

Features:
- Source tabs: SRM Memory | Local Files | Google Drive | Web Scrape
- Real-time digestion progress and stats
- Control when and what to digest
- Cortex node count tracking
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Handle both PyQt6 and PyQt5
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QCheckBox, QGroupBox, QProgressBar,
        QTabWidget, QWidget, QFrame, QScrollArea, QSplitter,
        QFileDialog, QTreeWidget, QTreeWidgetItem, QHeaderView
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon
    _QT_VERSION = 6
    _FontBold = QFont.Weight.Bold
    _AlignCenter = Qt.AlignmentFlag.AlignCenter
    _AlignLeft = Qt.AlignmentFlag.AlignLeft
    _Horizontal = Qt.Orientation.Horizontal
    _Vertical = Qt.Orientation.Vertical
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QCheckBox, QGroupBox, QProgressBar,
        QTabWidget, QWidget, QFrame, QScrollArea, QSplitter,
        QFileDialog, QTreeWidget, QTreeWidgetItem, QHeaderView
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon
    _QT_VERSION = 5
    _FontBold = QFont.Bold
    _AlignCenter = Qt.AlignCenter
    _AlignLeft = Qt.AlignLeft
    _Horizontal = Qt.Horizontal
    _Vertical = Qt.Vertical

# Paths
ROOT = Path(__file__).resolve().parents[3]


class SourceButton(QPushButton):
    """A button representing a knowledge source with status indicator."""

    def __init__(self, name: str, description: str, icon: str = "",
                 parent=None):
        display = f"{icon} {name}" if icon else name
        super().__init__(display, parent)
        self.source_name = name
        self.description = description
        self._done = False

        self.setMinimumHeight(45)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: 1px solid #555;
                border-radius: 4px;
                background: #333;
                color: #ddd;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #444;
                border-color: #9b59b6;
            }
            QPushButton:pressed {
                background: #555;
            }
        """)
        self.setToolTip(description)

    def mark_done(self):
        """Mark source as already processed."""
        self._done = True
        self.setText(f"{self.text()} [DONE]")
        self.setStyleSheet(self.styleSheet().replace(
            "background: #333", "background: #1a3a1a"))


class DigestionGUI(QDialog):
    """
    GUI for the KnowledgeDigestionFairy.

    Control panel for managing what knowledge gets digested into
    the Association Cortex on behalf of SourpatchesFairy.
    """

    # Signals for thread-safe updates
    log_message = pyqtSignal(str)
    stats_update = pyqtSignal(dict)

    def __init__(self, postal_hub=None, parent=None):
        super().__init__(parent)
        self._postal = postal_hub
        self._setup_ui()
        self._connect_signals()

        # Thread-safe signal connections
        self.log_message.connect(self._handle_log_message)
        self.stats_update.connect(self._handle_stats_update)

        # Stats polling timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_stats)
        self._poll_timer.start(5000)  # Every 5 seconds

        # Initial stats fetch
        self._poll_stats()

    def _setup_ui(self):
        """Build the entire UI."""
        self.setWindowTitle("Knowledge Digestion - Cortex Feed Control")
        self.setMinimumSize(800, 650)
        self.setStyleSheet("""
            QDialog {
                background: #2b2b2b;
                color: #ddd;
            }
            QLabel {
                color: #ddd;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background: #2b2b2b;
            }
            QTabBar::tab {
                background: #333;
                color: #aaa;
                padding: 8px 16px;
                border: 1px solid #555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
                color: #9b59b6;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 15px;
                color: #9b59b6;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Header ──
        header = QLabel("Knowledge Digestion - Cortex Feed Control")
        header_font = QFont("Segoe UI", 14)
        header_font.setWeight(_FontBold)
        header.setFont(header_font)
        header.setStyleSheet("color: #9b59b6; padding: 5px;")
        header.setAlignment(_AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("Feeding the Association Cortex on behalf of Sourpatches")
        subtitle.setStyleSheet("color: #888; font-style: italic; padding-bottom: 5px;")
        subtitle.setAlignment(_AlignCenter)
        layout.addWidget(subtitle)

        # ── Main Splitter ──
        splitter = QSplitter(_Vertical)

        # ── Top: Tabs ──
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_srm_tab(), "SRM Memory")
        self._tabs.addTab(self._create_local_tab(), "Local Files")
        self._tabs.addTab(self._create_gdrive_tab(), "Google Drive")
        self._tabs.addTab(self._create_scrape_tab(), "Web Scrape")
        splitter.addWidget(self._tabs)

        # ── Bottom: Stats + Log ──
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Stats bar
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(20)

        self._lbl_digested = QLabel("Digested: 0")
        self._lbl_queue = QLabel("Queue: 0")
        self._lbl_concepts = QLabel("Concepts: 0")
        self._lbl_cortex = QLabel("Cortex: ~39k nodes")
        self._lbl_errors = QLabel("Errors: 0")
        self._lbl_status = QLabel("Status: Ready")

        for lbl in [self._lbl_digested, self._lbl_queue, self._lbl_concepts,
                     self._lbl_cortex, self._lbl_errors, self._lbl_status]:
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            stats_layout.addWidget(lbl)

        self._lbl_status.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 11px;")
        bottom_layout.addWidget(stats_frame)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(0)  # Indeterminate
        self._progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 3px;
                background: #1e1e1e;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #9b59b6;
                border-radius: 3px;
            }
        """)
        self._progress.setVisible(False)
        bottom_layout.addWidget(self._progress)

        # Log output
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 10))
        self._log.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #ddd;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self._log.setMaximumHeight(180)
        bottom_layout.addWidget(self._log)

        # Control buttons
        btn_layout = QHBoxLayout()

        self._btn_stop = QPushButton("Stop All")
        self._btn_stop.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_all)

        self._btn_reset = QPushButton("Reset Progress")
        self._btn_reset.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: #e67e22; }
        """)
        self._btn_reset.clicked.connect(self._reset_progress)

        self._btn_close = QPushButton("Close")
        self._btn_close.setStyleSheet("""
            QPushButton {
                background: #555;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: #666; }
        """)
        self._btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_close)
        bottom_layout.addLayout(btn_layout)

        splitter.addWidget(bottom)
        splitter.setSizes([350, 300])
        layout.addWidget(splitter)

    # ──────────────────────────────────────────────────────────────────────
    # TAB: SRM Memory
    # ──────────────────────────────────────────────────────────────────────

    def _create_srm_tab(self) -> QWidget:
        """Create the SRM Memory feed tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        desc = QLabel(
            "Feed existing SRM memory cards into the Association Cortex.\n"
            "This processes creator_sessions and claude_office clusters.\n"
            "Auto-starts 30s after boot. Dedup-aware — safe to re-run."
        )
        desc.setStyleSheet("color: #888; padding: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Cluster buttons
        group = QGroupBox("Memory Clusters")
        g_layout = QVBoxLayout(group)

        self._btn_srm_all = SourceButton(
            "All Clusters", "Process creator_sessions + claude_office",
            icon="")
        self._btn_srm_all.clicked.connect(lambda: self._trigger_feed("bulk"))
        g_layout.addWidget(self._btn_srm_all)

        self._btn_srm_creator = SourceButton(
            "Creator Sessions", "Collaborative work sessions with Ace",
            icon="")
        self._btn_srm_creator.clicked.connect(
            lambda: self._trigger_feed("bulk", cluster="creator_sessions"))
        g_layout.addWidget(self._btn_srm_creator)

        self._btn_srm_office = SourceButton(
            "Claude Office", "Session logs, plans, notes, handoffs",
            icon="")
        self._btn_srm_office.clicked.connect(
            lambda: self._trigger_feed("bulk", cluster="claude_office"))
        g_layout.addWidget(self._btn_srm_office)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    # ──────────────────────────────────────────────────────────────────────
    # TAB: Local Files
    # ──────────────────────────────────────────────────────────────────────

    def _create_local_tab(self) -> QWidget:
        """Create the Local Files feed tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        desc = QLabel(
            "Digest local files into the Association Cortex.\n"
            "Text files are read directly. Images route to Visual Cortex.\n"
            "PDFs and DOCX are text-extracted where possible."
        )
        desc.setStyleSheet("color: #888; padding: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Preset directories
        group = QGroupBox("Preset Directories")
        g_layout = QVBoxLayout(group)

        self._btn_local_all = SourceButton(
            "All Local Sources",
            "Claude Office + From Ace + Screenshots",
            icon="")
        self._btn_local_all.clicked.connect(
            lambda: self._trigger_feed("local"))
        g_layout.addWidget(self._btn_local_all)

        self._btn_local_office = SourceButton(
            "Claude Office",
            "Session logs, plans, notes, handoffs, research",
            icon="")
        self._btn_local_office.clicked.connect(
            lambda: self._trigger_feed("local", directory="claude_office"))
        g_layout.addWidget(self._btn_local_office)

        self._btn_local_ace = SourceButton(
            "From Ace",
            "Field logs, proposals, PDFs, documents from Ace",
            icon="")
        self._btn_local_ace.clicked.connect(
            lambda: self._trigger_feed("local", directory="from_ace"))
        g_layout.addWidget(self._btn_local_ace)

        self._btn_local_screenshots = SourceButton(
            "Screenshots",
            "Screenshot images from Ace (routed to Visual Cortex)",
            icon="")
        self._btn_local_screenshots.clicked.connect(
            lambda: self._trigger_feed("local", directory="screenshots"))
        g_layout.addWidget(self._btn_local_screenshots)

        layout.addWidget(group)

        # Custom directory
        custom_group = QGroupBox("Custom Directory")
        custom_layout = QHBoxLayout(custom_group)

        self._local_path_input = QLineEdit()
        self._local_path_input.setPlaceholderText("Enter or browse for directory path...")
        self._local_path_input.setStyleSheet("""
            QLineEdit {
                background: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 6px;
                color: #ddd;
            }
        """)
        custom_layout.addWidget(self._local_path_input)

        btn_browse = QPushButton("Browse")
        btn_browse.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border-radius: 3px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #2980b9; }
        """)
        btn_browse.clicked.connect(self._browse_directory)
        custom_layout.addWidget(btn_browse)

        btn_digest = QPushButton("Digest")
        btn_digest.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #219a52; }
        """)
        btn_digest.clicked.connect(self._digest_custom_directory)
        custom_layout.addWidget(btn_digest)

        layout.addWidget(custom_group)
        layout.addStretch()
        return tab

    # ──────────────────────────────────────────────────────────────────────
    # TAB: Google Drive
    # ──────────────────────────────────────────────────────────────────────

    def _create_gdrive_tab(self) -> QWidget:
        """Create the Google Drive feed tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        desc = QLabel(
            "Feed Google Drive documents into the Association Cortex.\n"
            "The same content that's in Sourpatches' Personal.AI memory.\n"
            "Google Docs and Sheets are auto-converted to text."
        )
        desc.setStyleSheet("color: #888; padding: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        group = QGroupBox("Google Drive Feed")
        g_layout = QVBoxLayout(group)

        self._btn_gdrive_all = SourceButton(
            "All Google Drive (Root)",
            "Process all accessible Google Drive files recursively",
            icon="")
        self._btn_gdrive_all.clicked.connect(
            lambda: self._trigger_feed("gdrive", folder_id="root"))
        g_layout.addWidget(self._btn_gdrive_all)

        # Folder ID input
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Folder ID:"))
        self._gdrive_folder_input = QLineEdit()
        self._gdrive_folder_input.setPlaceholderText("Enter Google Drive folder ID...")
        self._gdrive_folder_input.setStyleSheet("""
            QLineEdit {
                background: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 6px;
                color: #ddd;
            }
        """)
        folder_layout.addWidget(self._gdrive_folder_input)

        btn_gdrive_folder = QPushButton("Feed Folder")
        btn_gdrive_folder.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #219a52; }
        """)
        btn_gdrive_folder.clicked.connect(self._feed_gdrive_folder)
        folder_layout.addWidget(btn_gdrive_folder)

        g_layout.addLayout(folder_layout)

        # Max files control
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max Files:"))
        self._gdrive_max_files = QSpinBox()
        self._gdrive_max_files.setRange(10, 10000)
        self._gdrive_max_files.setValue(100)
        self._gdrive_max_files.setStyleSheet("""
            QSpinBox {
                background: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: #ddd;
            }
        """)
        max_layout.addWidget(self._gdrive_max_files)
        max_layout.addStretch()
        g_layout.addLayout(max_layout)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    # ──────────────────────────────────────────────────────────────────────
    # TAB: Web Scrape
    # ──────────────────────────────────────────────────────────────────────

    def _create_scrape_tab(self) -> QWidget:
        """Create the Web Scrape tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        desc = QLabel(
            "Scrape web pages and feed content into the Association Cortex.\n"
            "Text is extracted, filtered through FirstEthicFilter, and digested.\n"
            "Images are routed to the Visual Cortex."
        )
        desc.setStyleSheet("color: #888; padding: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        group = QGroupBox("URL Scraping")
        g_layout = QVBoxLayout(group)

        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://example.com/article")
        self._url_input.setStyleSheet("""
            QLineEdit {
                background: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 6px;
                color: #ddd;
            }
        """)
        url_layout.addWidget(self._url_input)

        btn_scrape = QPushButton("Scrape & Digest")
        btn_scrape.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #219a52; }
        """)
        btn_scrape.clicked.connect(self._scrape_url)
        url_layout.addWidget(btn_scrape)

        g_layout.addLayout(url_layout)

        # Tags input
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Tags:"))
        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("comma, separated, tags")
        self._tags_input.setStyleSheet("""
            QLineEdit {
                background: #333;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 6px;
                color: #ddd;
            }
        """)
        tags_layout.addWidget(self._tags_input)
        g_layout.addLayout(tags_layout)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    # ──────────────────────────────────────────────────────────────────────
    # SIGNAL HANDLING
    # ──────────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        """Connect internal signals."""
        pass

    def _handle_log_message(self, msg: str):
        """Thread-safe log message display."""
        self._log.append(msg)
        # Auto-scroll
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End
                            if _QT_VERSION == 6 else QTextCursor.End)
        self._log.setTextCursor(cursor)

    def _handle_stats_update(self, stats: dict):
        """Thread-safe stats display update."""
        self._lbl_digested.setText(f"Digested: {stats.get('items_digested', 0)}")
        self._lbl_queue.setText(f"Queue: {stats.get('queue_size', 0)}")
        self._lbl_concepts.setText(f"Concepts: {stats.get('concepts_created', 0)}")
        self._lbl_errors.setText(f"Errors: {stats.get('errors', 0)}")

        # Status indicator
        if stats.get('bulk_mode_active') or stats.get('local_feed_active') or \
           stats.get('gdrive_mode_active') or stats.get('scrape_mode_active'):
            self._lbl_status.setText("Status: DIGESTING")
            self._lbl_status.setStyleSheet(
                "color: #f39c12; font-weight: bold; font-size: 11px;")
            self._progress.setVisible(True)
            self._btn_stop.setEnabled(True)
        elif stats.get('queue_size', 0) > 0:
            self._lbl_status.setText("Status: Processing Queue")
            self._lbl_status.setStyleSheet(
                "color: #3498db; font-weight: bold; font-size: 11px;")
            self._progress.setVisible(True)
            self._btn_stop.setEnabled(True)
        else:
            self._lbl_status.setText("Status: Ready")
            self._lbl_status.setStyleSheet(
                "color: #27ae60; font-weight: bold; font-size: 11px;")
            self._progress.setVisible(False)
            self._btn_stop.setEnabled(False)

    # ──────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ──────────────────────────────────────────────────────────────────────

    def _trigger_feed(self, feed_type: str, **kwargs):
        """Trigger a feed via postal system."""
        self._log_msg(f"Triggering {feed_type} feed... {kwargs}")

        if not self._postal:
            self._log_msg("WARNING: No postal connection. Cannot trigger feed.")
            return

        if feed_type == "bulk":
            self._postal.publish("knowledge.bulk_feed", {
                "cluster": kwargs.get("cluster", "all"),
            })

        elif feed_type == "local":
            directory = kwargs.get("directory", None)
            if directory:
                dirs = {}
                root = Path(__file__).resolve().parents[3]
                if directory == "claude_office":
                    dirs["claude_office"] = str(root / "Claude_Office")
                elif directory == "from_ace":
                    dirs["from_ace"] = str(root / "Claude_Office" / "from_ace")
                elif directory == "screenshots":
                    dirs["screenshots"] = str(root / "Claude_Office" / "from_ace" / "screen shots")
                self._postal.publish("knowledge.local_feed", {
                    "directories": dirs,
                    "reset": True,
                })
            else:
                self._postal.publish("knowledge.local_feed", {
                    "reset": True,
                })

        elif feed_type == "gdrive":
            folder_id = kwargs.get("folder_id", "root")
            max_files = self._gdrive_max_files.value() if hasattr(self, '_gdrive_max_files') else 100
            self._postal.publish("knowledge.gdrive_feed", {
                "folder_id": folder_id,
                "max_files": max_files,
            })

        elif feed_type == "scrape":
            url = kwargs.get("url", "")
            tags = kwargs.get("tags", [])
            self._postal.publish("knowledge.scrape", {
                "url": url,
                "tags": tags,
            })

    def _browse_directory(self):
        """Open file dialog to browse for a directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Directory to Digest",
            str(ROOT))
        if dir_path:
            self._local_path_input.setText(dir_path)

    def _digest_custom_directory(self):
        """Digest a custom directory path."""
        path = self._local_path_input.text().strip()
        if not path:
            self._log_msg("Please enter or browse for a directory path.")
            return
        if not os.path.isdir(path):
            self._log_msg(f"Not a valid directory: {path}")
            return

        dir_name = os.path.basename(path) or "custom"
        if self._postal:
            self._postal.publish("knowledge.local_feed", {
                "directories": {dir_name: path},
                "reset": False,
            })
            self._log_msg(f"Custom directory feed started: {path}")

    def _feed_gdrive_folder(self):
        """Feed a specific Google Drive folder."""
        folder_id = self._gdrive_folder_input.text().strip()
        if not folder_id:
            self._log_msg("Please enter a Google Drive folder ID.")
            return
        self._trigger_feed("gdrive", folder_id=folder_id)

    def _scrape_url(self):
        """Scrape a URL and feed into cortex."""
        url = self._url_input.text().strip()
        if not url:
            self._log_msg("Please enter a URL to scrape.")
            return
        if not url.startswith("http"):
            url = "https://" + url

        tags_text = self._tags_input.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []

        self._trigger_feed("scrape", url=url, tags=tags)

    def _stop_all(self):
        """Send stop signal to the digestion fairy."""
        self._log_msg("Sending stop signal...")
        if self._postal:
            self._postal.publish("knowledge.digest", {
                "command": "stop",
            })

    def _reset_progress(self):
        """Reset dedup state to allow re-processing."""
        self._log_msg("Resetting digestion progress...")
        # Clear the dedup state file
        dedup_file = ROOT / "state" / "knowledge_digestion_dedup.json"
        try:
            if dedup_file.exists():
                dedup_file.unlink()
                self._log_msg("Dedup state cleared. All sources will be re-processed.")
            else:
                self._log_msg("No dedup state file found.")
        except Exception as e:
            self._log_msg(f"Error clearing dedup: {e}")

    def _poll_stats(self):
        """Poll the fairy for current stats via postal intent."""
        if not self._postal:
            return

        # Try to get stats via intent
        try:
            # Publish a stats request — the fairy will respond
            self._postal.publish("fairy.intent", {
                "target": "KnowledgeDigestionFairy",
                "intent": "get_digestion_stats",
                "payload": {},
                "reply_to": "knowledge.digestion_stats_reply",
            })
        except Exception:
            pass

        # Also check dedup file directly for basic stats
        try:
            dedup_file = ROOT / "state" / "knowledge_digestion_dedup.json"
            if dedup_file.exists():
                with open(dedup_file, 'r') as f:
                    data = json.load(f)
                stats = {
                    "items_digested": data.get("items_digested", 0),
                    "srm_cards_processed": data.get("srm_cards_processed", 0),
                    "bulk_complete": data.get("bulk_complete", False),
                    "dedup_hashes_count": len(data.get("hashes", [])),
                }
                self.stats_update.emit(stats)
        except Exception:
            pass

    def _log_msg(self, msg: str):
        """Add a timestamped message to the log."""
        ts = time.strftime("%H:%M:%S")
        self.log_message.emit(f"[{ts}] {msg}")


# ──────────────────────────────────────────────────────────────────────────
# Standalone launcher
# ──────────────────────────────────────────────────────────────────────────

def launch_digestion_gui(postal_hub=None):
    """Launch the Knowledge Digestion GUI as a standalone window."""
    try:
        if _QT_VERSION == 6:
            from PyQt6.QtWidgets import QApplication
        else:
            from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        gui = DigestionGUI(postal_hub=postal_hub)
        gui.show()

        if not QApplication.instance().property("running"):
            app.exec() if _QT_VERSION == 6 else app.exec_()

        return gui
    except Exception as e:
        print(f"[DigestionGUI] Launch error: {e}")
        return None


if __name__ == "__main__":
    launch_digestion_gui()
