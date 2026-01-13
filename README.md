# Cogny 🧠
> **Your Intelligent Knowledge Base & Note Manager.**

<div align="center">
  <img src="assets/logo.png" alt="Cogny Logo" width="128">
</div>

**Cogny** is a powerful, hierarchical note-taking application designed for developers and power users. Built with Python and PySide6, it offers a seamless experience for organizing complex information, snippets, and documentation.

## 📸 Screenshots

### Main Interface
Manage your knowledge with a clean, dual-pane layout. The hierarchical tree lets you structure deep nested notes, while the editor supports rich Markdown formatting.
![Main Interface](assets/portada.png)

### Statistics & Insights
Visualize your writing habits and database growth.
![Statistics](assets/stats.png)

### Secure Vault
Keep sensitive information protected? *(Assuming boveda.png relates to this)*
![Vault](assets/boveda.png)

---

## ✨ Key Features

-   **Hierarchical Organization**: Create unlimited nested folders and notes. Drag and drop to reorganize effortlessly.
-   **Strict Structure Protection**: 
    -   Prevents accidental nesting into leaf notes (rebound logic).
    -   Folders act as containers (read-only) to keep structure clean.
-   **Rich Markdown Editor**:
    -   Syntax highlighting for code blocks (Python, SQL, Bash, etc.).
    -   Auto-formatting (lists, headers).
    -   **Code Copy**: One-click copy buttons for code snippets.
-   **User-Centric Zoom**:
    -   **Text Zoom**: Adjust font size independently (`Ctrl + / -`).
    -   **Image Zoom**: Scale images independently (`Ctrl + Shift + / -`).
    -   *No accidental Ctrl+Scroll zooming.*
-   **Modern UI**: Clean, light/dark theme support (customizable).

## 🚀 Getting Started

### Prerequisites
-   Python 3.10+
-   `pip install -r requirements.txt` (Mainly `PySide6`)

### Running the App
```bash
python main.py
```

## 🛠️ Configuration
-   **Database**: Notes are stored in `notes.cdb` (SQLite).
-   **Assets**: Images and attachments are managed internally.

## 📈 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Maalfer/cogny&type=Date)](https://star-history.com/#Maalfer/cogny&Date)

---
*Created by Mario.*
