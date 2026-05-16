from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.pipeline import TrackResult
from gui.generator_home import DEFAULT_MAP_VIEW, MapViewport
from gui.presentation import build_map_html


class _MapBridge(QObject):
    mapClicked = Signal(float, float)
    viewportChanged = Signal(float, float, int)

    @Slot(float, float)
    def reportMapClick(self, latitude: float, longitude: float) -> None:
        self.mapClicked.emit(latitude, longitude)

    @Slot(float, float, int)
    def reportViewportChange(self, latitude: float, longitude: float, zoom: int) -> None:
        self.viewportChanged.emit(latitude, longitude, zoom)


class TrackMapView(QWebEngineView):
    mapClicked = Signal(float, float)
    viewportChanged = Signal(float, float, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: TrackResult | None = None
        self._use_smoothed_coordinates = False
        self._color_by_speed = False
        self._picked_start: tuple[float, float] | None = None
        self._picked_end: tuple[float, float] | None = None
        self._active_pick_mode: str | None = None
        self._home_view = DEFAULT_MAP_VIEW
        self._bridge = _MapBridge(self)
        self._bridge.mapClicked.connect(self._emit_map_clicked)
        self._bridge.viewportChanged.connect(self._emit_viewport_changed)
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

    def set_home_view(self, view: MapViewport) -> None:
        self._home_view = view
        self._refresh_html()

    def home_view(self) -> MapViewport:
        return self._home_view

    def picked_points(self) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        return self._picked_start, self._picked_end

    def _emit_map_clicked(self, latitude: float, longitude: float) -> None:
        self.mapClicked.emit(latitude, longitude)

    def _emit_viewport_changed(self, latitude: float, longitude: float, zoom: int) -> None:
        self._home_view = MapViewport(latitude=latitude, longitude=longitude, zoom=zoom)
        self.viewportChanged.emit(latitude, longitude, zoom)

    def _refresh_html(self) -> None:
        self.setHtml(
            build_map_html(
                self._result,
                use_smoothed_coordinates=self._use_smoothed_coordinates,
                color_by_speed=self._color_by_speed,
                picked_start=self._picked_start,
                picked_end=self._picked_end,
                active_pick_mode=self._active_pick_mode,
                home_view=self._home_view,
            )
        )
