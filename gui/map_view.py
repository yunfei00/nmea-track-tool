from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.pipeline import TrackResult
from gui.presentation import build_map_html


class _MapBridge(QObject):
    mapClicked = Signal(float, float)

    @Slot(float, float)
    def reportMapClick(self, latitude: float, longitude: float) -> None:
        self.mapClicked.emit(latitude, longitude)


class TrackMapView(QWebEngineView):
    mapClicked = Signal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: TrackResult | None = None
        self._use_smoothed_coordinates = False
        self._color_by_speed = False
        self._picked_start: tuple[float, float] | None = None
        self._picked_end: tuple[float, float] | None = None
        self._active_pick_mode: str | None = None
        self._bridge = _MapBridge(self)
        self._bridge.mapClicked.connect(self._emit_map_clicked)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("mapBridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self._refresh_html()

    def set_track_result(
        self,
        result: TrackResult | None,
        *,
        use_smoothed_coordinates: bool = False,
        color_by_speed: bool = False,
    ) -> None:
        self._result = result
        self._use_smoothed_coordinates = use_smoothed_coordinates
        self._color_by_speed = color_by_speed
        self._refresh_html()

    def set_picked_points(
        self,
        *,
        start: tuple[float, float] | None = None,
        end: tuple[float, float] | None = None,
    ) -> None:
        self._picked_start = start
        self._picked_end = end
        self._refresh_html()

    def set_pick_mode(self, mode: str | None) -> None:
        self._active_pick_mode = mode
        self._refresh_html()

    def picked_points(self) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        return self._picked_start, self._picked_end

    def _emit_map_clicked(self, latitude: float, longitude: float) -> None:
        self.mapClicked.emit(latitude, longitude)

    def _refresh_html(self) -> None:
        self.setHtml(
            build_map_html(
                self._result,
                use_smoothed_coordinates=self._use_smoothed_coordinates,
                color_by_speed=self._color_by_speed,
                picked_start=self._picked_start,
                picked_end=self._picked_end,
                active_pick_mode=self._active_pick_mode,
            )
        )
