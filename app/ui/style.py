"""Helpers de estilo reutilizables para mejorar formas y tamaños sin cambiar colores.
Contiene funciones que devuelven estilos Qt compatibles usados por `widgets.py`.
"""
from typing import Literal

def button_style(theme: str, role: Literal['primary','danger','normal']='normal') -> str:
    """Devuelve un stylesheet para botones manteniendo la paleta pero con bordes y paddings mejorados."""
    radius = 10
    height = 36
    padding = "0 18px"

    if theme in ["Dark", "Dracula", "AnuPpuccin"]:
        if role == "primary":
            return f"""
                QPushButton {{
                    background-color: #3b82f6; 
                    color: white; 
                    border-radius: {radius}px;
                    padding: {padding};
                    font-weight: 600;
                    min-height: {height}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #2563eb; }}
                QPushButton:pressed {{ background-color: #1d4ed8; }}
            """
        if role == "danger":
            return f"""
                QPushButton {{
                    background-color: #ef4444; 
                    color: white; 
                    border-radius: {radius}px;
                    padding: {padding};
                    font-weight: 600;
                    min-height: {height}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #dc2626; }}
                QPushButton:pressed {{ background-color: #b91c1c; }}
            """
        # normal
        return f"""
            QPushButton {{
                background-color: #27272a; 
                color: #e4e4e7; 
                border: 1px solid #3f3f46;
                border-radius: {radius}px;
                padding: {padding};
                font-weight: 500;
                min-height: {height}px;
            }}
            QPushButton:hover {{ background-color: #3f3f46; }}
            QPushButton:pressed {{ background-color: #52525b; }}
        """
    else:
        if role == "primary":
            return f"""
                QPushButton {{
                    background-color: #2563eb; 
                    color: white; 
                    border-radius: {radius}px;
                    padding: {padding};
                    font-weight: 600;
                    min-height: {height}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #1d4ed8; }}
                QPushButton:pressed {{ background-color: #1e40af; }}
            """
        if role == "danger":
            return f"""
                QPushButton {{
                    background-color: #dc2626; 
                    color: white; 
                    border-radius: {radius}px;
                    padding: {padding};
                    font-weight: 600;
                    min-height: {height}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #b91c1c; }}
                QPushButton:pressed {{ background-color: #991b1b; }}
            """
        return f"""
            QPushButton {{
                background-color: #ffffff; 
                color: #18181b; 
                border: 1px solid #e4e4e7;
                border-radius: {radius}px;
                padding: {padding};
                font-weight: 500;
                min-height: {height}px;
            }}
            QPushButton:hover {{ background-color: #f4f4f5; }}
            QPushButton:pressed {{ background-color: #e4e4e7; border-color: #d4d4d8; }}
        """

def input_style(theme: str) -> str:
    radius = 10
    return f"""
        QLineEdit {{
            border-radius: {radius}px;
            padding: 10px;
            font-size: 14px;
        }}
        QLineEdit:focus {{ outline: none; }}
    """

def list_style(theme: str) -> str:
    radius = 8
    selected_bg = "#3b82f6" if theme in ["Dark", "Dracula", "AnuPpuccin"] else "#2563eb"
    return f"""
        QListWidget::item {{
            padding: 10px;
            border-radius: {radius}px;
        }}
        QListWidget::item:selected {{
            background-color: {selected_bg};
            color: white;
        }}
    """
