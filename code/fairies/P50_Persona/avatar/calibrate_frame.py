# Fairy Frame Calibration Tool
# P50_Persona/avatar/calibrate_frame.py
#
# A simple Qt tool to calibrate anchor positions for a fairy image.
# Click on the image to set anchor points for each body region.
#
# Usage:
#   python calibrate_frame.py path/to/fairy.png
#
# Saves calibration to: path/to/fairy_calibration.json

from __future__ import annotations

import os
import sys
import json
from typing import Dict, List, Optional, Tuple

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
        QSplitter, QMessageBox
    )
    from PyQt6.QtCore import Qt, QPoint, pyqtSignal
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QFont
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # Headless mode - define stubs for all Qt classes
    QApplication = QMainWindow = QWidget = QLabel = QPushButton = object
    QVBoxLayout = QHBoxLayout = QFileDialog = QListWidget = QListWidgetItem = object
    QSplitter = QMessageBox = QPixmap = QPainter = QColor = QPen = QFont = object
    QPoint = object
    pyqtSignal = lambda *a: property(lambda s: None)
    class _Qt:
        class AlignmentFlag:
            AlignCenter = AlignLeft = AlignRight = 0
        class AspectRatioMode:
            KeepAspectRatio = 0
        class TransformationMode:
            SmoothTransformation = 0
    Qt = _Qt()

from .fairy_frame import FairyRegion, DEFAULT_ANCHORS


class ImageCanvas(QLabel):
    """Canvas for displaying image and clicking anchor points."""
    
    clicked = pyqtSignal(float, float)  # Normalized x, y
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 400)
        self._pixmap: Optional[QPixmap] = None
        self._anchors: Dict[str, Tuple[float, float]] = {}
        self._current_region: Optional[str] = None
    
    def load_image(self, path: str) -> bool:
        """Load an image."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return False
        
        # Scale to fit while maintaining aspect ratio
        scaled = pixmap.scaled(
            600, 600,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._pixmap = scaled
        self._update_display()
        return True
    
    def set_anchors(self, anchors: Dict[str, any]) -> None:
        """Set current anchors."""
        self._anchors = {}
        for k, v in anchors.items():
            if isinstance(v, dict):
                # Paired region
                for side, pos in v.items():
                    self._anchors[f"{k}_{side}"] = pos
            else:
                self._anchors[k] = v
        self._update_display()
    
    def set_current_region(self, region: str) -> None:
        """Highlight which region we're setting."""
        self._current_region = region
        self._update_display()
    
    def _update_display(self) -> None:
        """Redraw with anchors."""
        if self._pixmap is None:
            return
        
        # Create copy to draw on
        display = self._pixmap.copy()
        painter = QPainter(display)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        w = display.width()
        h = display.height()
        
        # Draw each anchor
        for name, pos in self._anchors.items():
            x = int(pos[0] * w)
            y = int(pos[1] * h)
            
            # Color based on whether it's current
            if self._current_region and name.startswith(self._current_region):
                color = QColor(255, 100, 100)  # Red for current
                size = 12
            else:
                color = QColor(100, 200, 255)  # Blue for others
                size = 8
            
            # Draw circle
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPoint(x, y), size, size)
            
            # Draw crosshair
            painter.drawLine(x - size - 2, y, x - 4, y)
            painter.drawLine(x + 4, y, x + size + 2, y)
            painter.drawLine(x, y - size - 2, x, y - 4)
            painter.drawLine(x, y + 4, x, y + size + 2)
            
            # Label
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.drawText(x + size + 4, y + 4, name)
        
        painter.end()
        self.setPixmap(display)
    
    def mousePressEvent(self, event) -> None:
        """Handle click to set anchor."""
        if self._pixmap is None:
            return
        
        # Get click position relative to pixmap
        pos = event.position()
        
        # Calculate offset (pixmap is centered in label)
        label_w = self.width()
        label_h = self.height()
        pix_w = self._pixmap.width()
        pix_h = self._pixmap.height()
        
        offset_x = (label_w - pix_w) / 2
        offset_y = (label_h - pix_h) / 2
        
        # Normalize to 0-1
        x = (pos.x() - offset_x) / pix_w
        y = (pos.y() - offset_y) / pix_h
        
        if 0 <= x <= 1 and 0 <= y <= 1:
            self.clicked.emit(x, y)


class CalibrationWindow(QMainWindow):
    """Main calibration window."""
    
    def __init__(self, image_path: str = None):
        super().__init__()
        self.setWindowTitle("Fairy Frame Calibration")
        self.setMinimumSize(900, 600)
        
        self._image_path = image_path
        self._anchors: Dict[str, any] = {}
        self._current_region = None
        self._current_side = None
        
        # Load defaults
        for region in FairyRegion:
            default = DEFAULT_ANCHORS.get(region)
            if isinstance(default, dict):
                self._anchors[region.value] = default.copy()
            else:
                self._anchors[region.value] = default
        
        self._setup_ui()
        
        if image_path:
            self._load_image(image_path)
    
    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        
        # Left: Image canvas
        self.canvas = ImageCanvas()
        self.canvas.clicked.connect(self._on_canvas_click)
        
        # Right: Controls
        controls = QWidget()
        ctrl_layout = QVBoxLayout(controls)
        
        # Region list
        ctrl_layout.addWidget(QLabel("Regions (click to select):"))
        self.region_list = QListWidget()
        
        for region in FairyRegion:
            default = DEFAULT_ANCHORS.get(region)
            if isinstance(default, dict):
                # Paired region
                for side in ["left", "right"]:
                    item = QListWidgetItem(f"{region.value}_{side}")
                    self.region_list.addItem(item)
            else:
                item = QListWidgetItem(region.value)
                self.region_list.addItem(item)
        
        self.region_list.currentItemChanged.connect(self._on_region_selected)
        ctrl_layout.addWidget(self.region_list)
        
        # Instructions
        ctrl_layout.addWidget(QLabel(""))
        self.instructions = QLabel("Select a region, then click on the image\nto set its anchor position.")
        self.instructions.setWordWrap(True)
        ctrl_layout.addWidget(self.instructions)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        load_btn = QPushButton("Load Image...")
        load_btn.clicked.connect(self._load_image_dialog)
        btn_layout.addWidget(load_btn)
        
        save_btn = QPushButton("Save Calibration")
        save_btn.clicked.connect(self._save_calibration)
        btn_layout.addWidget(save_btn)
        
        ctrl_layout.addLayout(btn_layout)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        ctrl_layout.addWidget(reset_btn)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(controls)
        splitter.setSizes([600, 300])
        
        layout.addWidget(splitter)
    
    def _load_image_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fairy Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if path:
            self._load_image(path)
    
    def _load_image(self, path: str) -> None:
        if self.canvas.load_image(path):
            self._image_path = path
            self.setWindowTitle(f"Calibration: {os.path.basename(path)}")
            self._update_canvas()
        else:
            QMessageBox.warning(self, "Error", f"Failed to load image: {path}")
    
    def _on_region_selected(self, current, previous) -> None:
        if current is None:
            self._current_region = None
            self._current_side = None
            return
        
        name = current.text()
        if "_" in name:
            self._current_region, self._current_side = name.rsplit("_", 1)
        else:
            self._current_region = name
            self._current_side = None
        
        self.canvas.set_current_region(self._current_region)
        self.instructions.setText(f"Click on the image to set\n{name} position")
    
    def _on_canvas_click(self, x: float, y: float) -> None:
        if self._current_region is None:
            return
        
        pos = (round(x, 3), round(y, 3))
        
        if self._current_side:
            # Paired region
            if not isinstance(self._anchors.get(self._current_region), dict):
                self._anchors[self._current_region] = {"left": (0.3, 0.5), "right": (0.7, 0.5)}
            self._anchors[self._current_region][self._current_side] = pos
        else:
            self._anchors[self._current_region] = pos
        
        self._update_canvas()
        
        # Auto-advance to next region
        current_row = self.region_list.currentRow()
        if current_row < self.region_list.count() - 1:
            self.region_list.setCurrentRow(current_row + 1)
    
    def _update_canvas(self) -> None:
        flat = {}
        for k, v in self._anchors.items():
            if isinstance(v, dict):
                for side, pos in v.items():
                    flat[f"{k}_{side}"] = pos
            else:
                flat[k] = v
        self.canvas.set_anchors(flat)
    
    def _reset_defaults(self) -> None:
        for region in FairyRegion:
            default = DEFAULT_ANCHORS.get(region)
            if isinstance(default, dict):
                self._anchors[region.value] = default.copy()
            else:
                self._anchors[region.value] = default
        self._update_canvas()
    
    def _save_calibration(self) -> None:
        if not self._image_path:
            QMessageBox.warning(self, "Error", "No image loaded")
            return
        
        # Default save path
        base = os.path.splitext(self._image_path)[0]
        save_path = f"{base}_calibration.json"
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration",
            save_path,
            "JSON files (*.json)"
        )
        
        if not path:
            return
        
        data = {
            "name": os.path.basename(self._image_path),
            "base_image": self._image_path,
            "anchors": self._anchors,
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        
        QMessageBox.information(self, "Saved", f"Calibration saved to:\n{path}")


def main():
    app = QApplication(sys.argv)
    
    # Get image path from command line
    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    window = CalibrationWindow(image_path)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
