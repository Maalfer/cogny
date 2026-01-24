from abc import ABC, abstractmethod
from PySide6.QtGui import QPalette, QColor

class BaseTheme(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        """Configure the QPalette for this theme."""
        pass

    @abstractmethod
    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        pass

    @abstractmethod
    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        pass

    @abstractmethod
    def get_code_bg_color(self) -> QColor:
        pass

    @abstractmethod
    def get_syntax_colors(self) -> dict:
        pass

    @abstractmethod
    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        pass

    @abstractmethod
    def get_splitter_style(self) -> str:
        pass

    @abstractmethod
    def get_toolbar_style(self, global_bg: str = None) -> str:
        pass

    @abstractmethod
    def get_scrollbar_style(self) -> str:
        pass

    @abstractmethod
    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        pass

    @abstractmethod
    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        pass

    @abstractmethod
    def get_tab_style(self, global_bg: str = None) -> str:
        pass
