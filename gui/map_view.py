from __future__ import annotations

from PySide6.QtWebEngineWidgets import QWebEngineView

from core.pipeline import TrackResult
from gui.presentation import build_map_html


class TrackMapView(QWebEngineView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHtml(build_map_html(None))

    def set_track_result(
        self,
        result: TrackResult | None,
        *,
        use_smoothed_coordinates: bool = False,
        color_by_speed: bool = False,
    ) -> None:
        self.setHtml(
            build_map_html(
                result,
                use_smoothed_coordinates=use_smoothed_coordinates,
                color_by_speed=color_by_speed,
            )
        )
