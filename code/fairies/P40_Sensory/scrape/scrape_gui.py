"""
ScrapeFairy GUI - Knowledge Acquisition Interface

Provides a GUI for configuring and running web scrapes to train knowledge into memory.
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Dict, Any

# Handle both PyQt6 and PyQt5
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
        QProgressBar, QTabWidget, QWidget, QListWidget, QListWidgetItem,
        QMessageBox, QFrame
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QColor, QTextCursor
    _QT_VERSION = 6
    _FontBold = QFont.Weight.Bold
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
        QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
        QProgressBar, QTabWidget, QWidget, QListWidget, QListWidgetItem,
        QMessageBox, QFrame
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QColor, QTextCursor
    _QT_VERSION = 5
    _FontBold = QFont.Bold

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fairies.P40_Sensory.scrape.scrape_fairy import (
    ScrapeFairy, ScrapeConfig, SourceType,
    get_scrape_fairy, get_iep_config, get_sep_config,
    get_gutenberg_config, get_gutenberg_philosophy_config, get_gutenberg_fiction_config
)

# Memory card counter
try:
    from fairies.P10_Memory.tools.memory_card_counter import get_card_count_simple, count_memory_cards
    HAS_MEMORY_COUNTER = True
except ImportError:
    HAS_MEMORY_COUNTER = False
    def get_card_count_simple(): return 0
    def count_memory_cards(): return {}


class ScrapeGUI(QDialog):
    """
    GUI for the ScrapeFairy knowledge acquisition system.
    
    Features:
    - Preset configurations (IEP, SEP)
    - Custom URL/API scraping
    - Real-time progress logging
    - Statistics display
    """
    
    # Signals for thread-safe updates
    scrape_started = pyqtSignal()
    scrape_finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)  # Thread-safe logging
    progress_update = pyqtSignal(dict)  # Thread-safe progress
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fairy = get_scrape_fairy()
        self._setup_ui()
        self._connect_signals()
        
        # Connect thread-safe signals to handlers
        self.log_message.connect(self._handle_log_message)
        self.progress_update.connect(self._handle_progress_update)
        
        # Poll timer for progress updates
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_progress)
        
        # Memory counter timer (update every 10 seconds)
        self._memory_timer = QTimer()
        self._memory_timer.timeout.connect(self._update_memory_count)
        self._memory_timer.start(10000)  # 10 seconds
        
        # Initial memory count
        self._update_memory_count()
    
    def _setup_ui(self):
        """Build the UI."""
        self.setWindowTitle(" ScrapeFairy - Knowledge Acquisition")
        self.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # ════════════════════════════════════════════════════════════════════
        # Header
        # ════════════════════════════════════════════════════════════════════
        header = QLabel(" ScrapeFairy - Train Knowledge into Memory")
        header.setFont(QFont("Segoe UI", 14, _FontBold))
        header.setStyleSheet("color: #9b59b6; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # ════════════════════════════════════════════════════════════════════
        # Tabs: Presets | Custom | API
        # ════════════════════════════════════════════════════════════════════
        tabs = QTabWidget()
        
        # --- Presets Tab ---
        presets_tab = QWidget()
        presets_layout = QVBoxLayout(presets_tab)
        
        presets_label = QLabel("Quick-start with curated knowledge sources:")
        presets_layout.addWidget(presets_label)
        
        # Preset buttons
        preset_grid = QGridLayout()
        
        self.iep_btn = QPushButton(" Internet Encyclopedia of Philosophy\n~900 articles")
        self.iep_btn.setMinimumHeight(60)
        self.iep_btn.setStyleSheet("text-align: left; padding: 10px;")
        preset_grid.addWidget(self.iep_btn, 0, 0)
        
        self.sep_btn = QPushButton(" Stanford Encyclopedia of Philosophy\n~1,774 articles")
        self.sep_btn.setMinimumHeight(60)
        self.sep_btn.setStyleSheet("text-align: left; padding: 10px;")
        preset_grid.addWidget(self.sep_btn, 0, 1)
        
        self.gutenberg_btn = QPushButton(" Project Gutenberg\n70,000+ classic texts")
        self.gutenberg_btn.setMinimumHeight(60)
        self.gutenberg_btn.setStyleSheet("text-align: left; padding: 10px;")
        preset_grid.addWidget(self.gutenberg_btn, 1, 0)
        
        self.philosophers_api_btn = QPushButton(" Philosophers API\nStructured philosopher data")
        self.philosophers_api_btn.setMinimumHeight(60)
        self.philosophers_api_btn.setStyleSheet("text-align: left; padding: 10px;")
        preset_grid.addWidget(self.philosophers_api_btn, 1, 1)
        
        presets_layout.addLayout(preset_grid)
        presets_layout.addStretch()
        
        tabs.addTab(presets_tab, " Presets")
        
        # --- Custom Website Tab ---
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        
        # URL input
        url_group = QGroupBox("Target Website")
        url_layout = QGridLayout(url_group)
        
        url_layout.addWidget(QLabel("Start URL:"), 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/articles/")
        url_layout.addWidget(self.url_input, 0, 1)
        
        url_layout.addWidget(QLabel("Job Name:"), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Knowledge Source")
        url_layout.addWidget(self.name_input, 1, 1)
        
        url_layout.addWidget(QLabel("Domain Tag:"), 2, 0)
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("philosophy, science, history...")
        url_layout.addWidget(self.domain_input, 2, 1)
        
        custom_layout.addWidget(url_group)
        
        # Options
        options_group = QGroupBox("Crawl Options")
        options_layout = QGridLayout(options_group)
        
        options_layout.addWidget(QLabel("Max Pages:"), 0, 0)
        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 10000)
        self.max_pages_spin.setValue(100)
        options_layout.addWidget(self.max_pages_spin, 0, 1)
        
        options_layout.addWidget(QLabel("Max Depth:"), 0, 2)
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(1, 10)
        self.max_depth_spin.setValue(3)
        options_layout.addWidget(self.max_depth_spin, 0, 3)
        
        options_layout.addWidget(QLabel("Delay (sec):"), 1, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 10.0)
        self.delay_spin.setValue(1.5)
        self.delay_spin.setSingleStep(0.5)
        options_layout.addWidget(self.delay_spin, 1, 1)
        
        self.follow_links_check = QCheckBox("Follow Links")
        self.follow_links_check.setChecked(True)
        options_layout.addWidget(self.follow_links_check, 1, 2, 1, 2)
        
        custom_layout.addWidget(options_group)
        
        # Selectors (advanced)
        selectors_group = QGroupBox("Content Selectors (Advanced)")
        selectors_layout = QGridLayout(selectors_group)
        
        selectors_layout.addWidget(QLabel("Content:"), 0, 0)
        self.content_selector = QLineEdit()
        self.content_selector.setText("article, .content, .entry-content, main")
        selectors_layout.addWidget(self.content_selector, 0, 1)
        
        selectors_layout.addWidget(QLabel("Title:"), 1, 0)
        self.title_selector = QLineEdit()
        self.title_selector.setText("h1, .entry-title, title")
        selectors_layout.addWidget(self.title_selector, 1, 1)
        
        selectors_layout.addWidget(QLabel("URL Pattern:"), 2, 0)
        self.url_pattern = QLineEdit()
        self.url_pattern.setPlaceholderText("Regex to filter URLs (optional)")
        selectors_layout.addWidget(self.url_pattern, 2, 1)
        
        custom_layout.addWidget(selectors_group)
        
        # Start button for custom
        self.custom_start_btn = QPushButton(" Start Custom Scrape")
        self.custom_start_btn.setMinimumHeight(40)
        self.custom_start_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        custom_layout.addWidget(self.custom_start_btn)
        
        custom_layout.addStretch()
        tabs.addTab(custom_tab, " Custom Website")
        
        # --- API Tab ---
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        
        api_group = QGroupBox("JSON API Endpoint")
        api_inner = QGridLayout(api_group)
        
        api_inner.addWidget(QLabel("API URL:"), 0, 0)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://api.example.com/articles")
        api_inner.addWidget(self.api_url_input, 0, 1)
        
        api_inner.addWidget(QLabel("Job Name:"), 1, 0)
        self.api_name_input = QLineEdit()
        self.api_name_input.setPlaceholderText("API Knowledge Source")
        api_inner.addWidget(self.api_name_input, 1, 1)
        
        api_inner.addWidget(QLabel("Domain Tag:"), 2, 0)
        self.api_domain_input = QLineEdit()
        api_inner.addWidget(self.api_domain_input, 2, 1)
        
        api_layout.addWidget(api_group)
        
        api_info = QLabel(
            "The API should return JSON with an array of items.\n"
            "Each item should have 'title' and 'content' (or similar) fields."
        )
        api_info.setStyleSheet("color: #666; font-style: italic;")
        api_layout.addWidget(api_info)
        
        self.api_start_btn = QPushButton(" Fetch from API")
        self.api_start_btn.setMinimumHeight(40)
        self.api_start_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        api_layout.addWidget(self.api_start_btn)
        
        api_layout.addStretch()
        tabs.addTab(api_tab, " API")
        
        layout.addWidget(tabs)
        
        # ════════════════════════════════════════════════════════════════════
        # Memory Card Counter
        # ════════════════════════════════════════════════════════════════════
        memory_group = QGroupBox(" Memory Status")
        memory_layout = QHBoxLayout(memory_group)
        
        self.memory_cards_label = QLabel("Memory Cards: ...")
        self.memory_cards_label.setStyleSheet("font-weight: bold; color: #9b59b6;")
        memory_layout.addWidget(self.memory_cards_label)
        
        self.memory_size_label = QLabel("Size: ...")
        memory_layout.addWidget(self.memory_size_label)
        
        memory_layout.addStretch()
        
        self.refresh_memory_btn = QPushButton(" Refresh")
        self.refresh_memory_btn.clicked.connect(self._update_memory_count)
        memory_layout.addWidget(self.refresh_memory_btn)
        
        layout.addWidget(memory_group)
        
        # ════════════════════════════════════════════════════════════════════
        # Progress Section
        # ════════════════════════════════════════════════════════════════════
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        # Stats bar
        stats_layout = QHBoxLayout()
        
        self.pages_label = QLabel("Pages: 0")
        self.pages_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.pages_label)
        
        self.words_label = QLabel("Words: 0")
        self.words_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.words_label)
        
        self.errors_label = QLabel("Errors: 0")
        self.errors_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
        stats_layout.addWidget(self.errors_label)
        
        stats_layout.addStretch()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #27ae60;")
        stats_layout.addWidget(self.status_label)
        
        progress_layout.addLayout(stats_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        self.log_output.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; background-color: #1e1e1e; color: #ddd;")
        progress_layout.addWidget(self.log_output)
        
        layout.addWidget(progress_group)
        
        # ════════════════════════════════════════════════════════════════════
        # Control Buttons
        # ════════════════════════════════════════════════════════════════════
        button_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton("[Stop]")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Preset buttons
        self.iep_btn.clicked.connect(lambda: self._start_preset("iep"))
        self.sep_btn.clicked.connect(lambda: self._start_preset("sep"))
        self.gutenberg_btn.clicked.connect(lambda: self._start_preset("gutenberg"))
        self.philosophers_api_btn.clicked.connect(lambda: self._start_preset("philosophers"))
        
        # Custom/API buttons
        self.custom_start_btn.clicked.connect(self._start_custom)
        self.api_start_btn.clicked.connect(self._start_api)
        
        # Control buttons
        self.stop_btn.clicked.connect(self._stop_scrape)
        self.close_btn.clicked.connect(self.close)
    
    def _start_preset(self, preset_name: str):
        """Start a preset scrape configuration."""
        if preset_name == "iep":
            config = get_iep_config()
        elif preset_name == "sep":
            config = get_sep_config()
        elif preset_name == "gutenberg":
            config = get_gutenberg_config()
        elif preset_name == "philosophers":
            config = ScrapeConfig(
                name="Philosophers API",
                source_type=SourceType.API_JSON,
                start_url="https://philosophersapi.com/api/philosophers",
                knowledge_domain="philosophy",
                knowledge_kind="system.knowledge.philosophy",
            )
        else:
            return
        
        self._start_scrape(config)
    
    def _start_custom(self):
        """Start a custom website scrape."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a start URL.")
            return
        
        name = self.name_input.text().strip() or "Custom Scrape"
        domain = self.domain_input.text().strip() or "general"
        
        url_patterns = []
        pattern = self.url_pattern.text().strip()
        if pattern:
            url_patterns.append(pattern)
        
        config = ScrapeConfig(
            name=name,
            source_type=SourceType.WEBSITE,
            start_url=url,
            follow_links=self.follow_links_check.isChecked(),
            max_pages=self.max_pages_spin.value(),
            max_depth=self.max_depth_spin.value(),
            delay_seconds=self.delay_spin.value(),
            content_selector=self.content_selector.text(),
            title_selector=self.title_selector.text(),
            url_patterns=url_patterns,
            knowledge_domain=domain,
            knowledge_kind=f"system.knowledge.{domain}",
        )
        
        self._start_scrape(config)
    
    def _start_api(self):
        """Start an API scrape."""
        url = self.api_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter an API URL.")
            return
        
        name = self.api_name_input.text().strip() or "API Scrape"
        domain = self.api_domain_input.text().strip() or "general"
        
        config = ScrapeConfig(
            name=name,
            source_type=SourceType.API_JSON,
            start_url=url,
            knowledge_domain=domain,
            knowledge_kind=f"system.knowledge.{domain}",
        )
        
        self._start_scrape(config)
    
    def _start_scrape(self, config: ScrapeConfig):
        """Start a scrape with the given config."""
        if self.fairy.is_running():
            QMessageBox.warning(self, "Busy", "A scrape is already in progress.")
            return
        
        self.log_output.clear()
        self._log(f"Starting: {config.name}")
        self._log(f"URL: {config.start_url}")
        
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet("color: #f39c12;")
        self.progress_bar.setVisible(True)
        self.stop_btn.setEnabled(True)
        
        # Disable start buttons
        self._set_buttons_enabled(False)
        
        # Thread-safe callbacks via signals
        def log_callback(msg):
            self.log_message.emit(msg)
        
        def progress_callback(stats):
            self.progress_update.emit(stats)
        
        # Start the scrape with thread-safe callbacks
        self.fairy.start_scrape(
            config,
            progress_callback=progress_callback,
            log_callback=log_callback
        )
        
        # Start polling
        self._poll_timer.start(500)
        
        self.scrape_started.emit()
    
    def _stop_scrape(self):
        """Stop the current scrape."""
        self.fairy.stop_scrape()
        self._log("Stopping...")
    
    def _check_progress(self):
        """Check if scrape is still running."""
        if not self.fairy.is_running():
            self._poll_timer.stop()
            self._on_scrape_finished()
    
    def _on_progress(self, stats: Dict[str, Any]):
        """Handle progress update."""
        self.pages_label.setText(f"Pages: {stats['pages_ingested']}")
        self.words_label.setText(f"Words: {stats['total_words']:,}")
        self.errors_label.setText(f"Errors: {stats['errors']}")
    
    def _on_scrape_finished(self):
        """Handle scrape completion."""
        stats = self.fairy.get_stats()
        
        self.status_label.setText("Complete!")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        
        self._set_buttons_enabled(True)
        
        # Final stats
        self._on_progress(stats)
        
        duration = (stats["end_time"] or 0) - (stats["start_time"] or 0)
        self._log(f"[DONE] Complete: {stats['pages_ingested']} pages, {stats['total_words']:,} words in {duration:.1f}s")
        self._log("")
        self._log(" Scrape finished! You may close this window or start another.")
        
        self.scrape_finished.emit(stats)
    
    def _handle_log_message(self, message: str):
        """Thread-safe log handler - runs on main thread."""
        self._log(message)
    
    def _handle_progress_update(self, stats: Dict[str, Any]):
        """Thread-safe progress handler - runs on main thread."""
        self._on_progress(stats)
    
    def _log(self, message: str):
        """Add a message to the log."""
        self.log_output.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _set_buttons_enabled(self, enabled: bool):
        """Enable/disable start buttons."""
        self.iep_btn.setEnabled(enabled)
        self.sep_btn.setEnabled(enabled)
        self.gutenberg_btn.setEnabled(enabled)
        self.philosophers_api_btn.setEnabled(enabled)
        self.custom_start_btn.setEnabled(enabled)
        self.api_start_btn.setEnabled(enabled)
    
    def _update_memory_count(self):
        """Update the memory card counter display."""
        try:
            stats = count_memory_cards()
            if "error" in stats:
                self.memory_cards_label.setText("Memory Cards: N/A")
                self.memory_size_label.setText("")
            else:
                total = stats.get("total_cards", 0)
                size_mb = stats.get("total_size_mb", 0)
                self.memory_cards_label.setText(f"Memory Cards: {total:,}")
                self.memory_size_label.setText(f"Size: {size_mb:.1f} MB")
        except Exception as e:
            self.memory_cards_label.setText(f"Memory Cards: Error")
            self.memory_size_label.setText(str(e)[:30])


# ============================================================================
# Standalone test
# ============================================================================

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #ddd;
        }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            color: #9b59b6;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 5px;
        }
        QPushButton {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 8px 15px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #666;
        }
        QTabWidget::pane {
            border: 1px solid #444;
        }
        QTabBar::tab {
            background-color: #3c3c3c;
            padding: 8px 15px;
            border: 1px solid #444;
        }
        QTabBar::tab:selected {
            background-color: #4a4a4a;
        }
    """)
    
    dialog = ScrapeGUI()
    dialog.show()
    
    sys.exit(app.exec_())
