from PySide6.QtCore import QObject, QEvent, Qt, QPoint
from PySide6.QtGui import QCursor, QMouseEvent

class WindowResizeHandler(QObject):
    """
    Handles frameless window resizing logic.
    """
    def __init__(self, window, resize_margin=5):
        super().__init__(window)
        self._window = window
        self._resize_margin = resize_margin
        
        # Install event filter on the window
        # Note: If filtering global application, the logic might differ slightly,
        # but here we attach to the specific window instance logic.
        # Original code used QApplication.instance().installEventFilter(self)
        # We can replicate that or just filter the window if events propagate correctly.
        # However, for frameless windows, catching Hover/Move often needs robust filtering.
        # We will keep the pattern of being called from the Window's eventFilter or 
        # installing it on the window.
        pass

    def handle_event(self, obj, event):
        """
        Main entry point for filtering events.
        Returns True if event is handled.
        """
        if self._window.isMaximized():
            return False

        if event.type() == QEvent.MouseMove:
            if self._check_resize_area(event.globalPosition().toPoint()):
                return True
                
        elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            edges = self._get_edges(event.globalPosition().toPoint())
            if edges:
                self._start_system_resize(edges)
                return True
                
        return False

    def _check_resize_area(self, global_pos):
        edges = self._get_edges(global_pos)
        
        if edges:
            if edges == (True, False, False, False): # Left
                self._window.setCursor(Qt.SizeHorCursor)
            elif edges == (False, True, False, False): # Right
                self._window.setCursor(Qt.SizeHorCursor)
            elif edges == (False, False, True, False): # Top
                self._window.setCursor(Qt.SizeVerCursor)
            elif edges == (False, False, False, True): # Bottom
                self._window.setCursor(Qt.SizeVerCursor)
            elif edges == (True, False, True, False): # Top-Left
                self._window.setCursor(Qt.SizeFDiagCursor)
            elif edges == (False, True, True, False): # Top-Right
                self._window.setCursor(Qt.SizeBDiagCursor)
            elif edges == (True, False, False, True): # Bottom-Left
                self._window.setCursor(Qt.SizeBDiagCursor)
            elif edges == (False, True, False, True): # Bottom-Right
                self._window.setCursor(Qt.SizeFDiagCursor)
            return True
        else:
            # Clear our cursor if currently set to a resize shape
            current_shape = self._window.cursor().shape()
            if current_shape in [Qt.SizeHorCursor, Qt.SizeVerCursor, Qt.SizeFDiagCursor, Qt.SizeBDiagCursor]:
                 self._window.setCursor(Qt.ArrowCursor)
            return False

    def _get_edges(self, global_pos):
        # Map global to local
        local_pos = self._window.mapFromGlobal(global_pos)
        rect = self._window.rect()
        m = self._resize_margin
        
        x = local_pos.x()
        y = local_pos.y()
        w = rect.width()
        h = rect.height()
        
        left = x <= m
        right = x >= w - m
        top = y <= m
        bottom = y >= h - m
        
        if left or right or top or bottom:
            return (left, right, top, bottom)
        return None

    def _start_system_resize(self, edges):
        left, right, top, bottom = edges
        edge = None
        
        if top and left: edge = Qt.TopEdge | Qt.LeftEdge
        elif top and right: edge = Qt.TopEdge | Qt.RightEdge
        elif bottom and left: edge = Qt.BottomEdge | Qt.LeftEdge
        elif bottom and right: edge = Qt.BottomEdge | Qt.RightEdge
        elif left: edge = Qt.LeftEdge
        elif right: edge = Qt.RightEdge
        elif top: edge = Qt.TopEdge
        elif bottom: edge = Qt.BottomEdge
        
        if edge:
             window_handle = self._window.windowHandle()
             if window_handle:
                  window_handle.startSystemResize(edge)
