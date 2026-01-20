# Splash Screen & Initialization Logic (Protected)

**CRITICAL COMPONENT**: This document describes the "protected" initialization flow responsible for the fluid startup experience. 
**DO NOT MODIFY** the core principles of this flow without understanding the consequences (flickering, double-loading, slow startup perception).

## Core Principles

1.  **Splash as Authoritative Loader**: The Splash Screen is not just a visual mask; it is the *controller* of the initial load. It does not close until the application is **fully ready**.
2.  **Async "Warmup"**: The application performs heavy imports and caches regex/styles in a background thread (`WarmupWorker`) *before* even creating the `MainWindow`.
3.  **Preload Note (Async)**: Once `MainWindow` is created, it is kept hidden. The splash triggers `window.preload_initial_state()`. This method specifically loads the last used note (or a fallback) using `async_load=True`.
4.  **Minimum Duration**: To prevent a jarring "flash" on fast systems, the splash enforces a minimum display time (e.g., 1.5s).
5.  **Single Source of Truth**: The `restore_state` logic in `MainWindow` (which usually restores sidebar selection) is **DISABLED** for note selection. Only the splash preload logic is allowed to load the initial note.

## The Flow

1.  `main.py` starts `SplashWindow`.
2.  `SplashWindow` runs `WarmupWorker`.
3.  `WarmupWorker` finishes -> emits signal -> calls `launch_main_app`.
4.  `launch_main_app`:
    -   Creates `MainWindow` (Hidden).
    -   Calls `window.preload_initial_state()`.
5.  `preload_initial_state`:
    -   Checks `config.json` for `last_opened_note`.
    -   **IF EXIST**: Starts loading it (`async_load=True`).
    -   **IF MISSING**: Searches vault for *any* `.md` file (Fallback) and starts loading it.
    -   **IF EMPTY VAULT**: Emits `ready` immediately.
6.  `EditorArea` loads content and preloads images in background.
7.  `EditorArea` emits `note_loaded`.
8.  `MainWindow._on_preload_finished`:
    -   **Silently** syncs Sidebar selection (`blockSignals(True)`).
    -   Emits `ready`.
9.  `main.show_and_close_splash`:
    -   Checks elapsed time.
    -   Waits if needed (to meet 1.5s minimum).
    -   shows `MainWindow`, closes `Splash`.

## Common Pitfalls (Regressions to Avoid)

-   **Double Loading**: If `UiStateMixin.restore_state` tries to select the last note, it triggers the Sidebar's `selectionChanged` signal, which triggers a *second* load in the Editor. This overrides the splash preload and causes a visible refresh/flicker. **Keep note restoration disabled in `restore_state`.**
-   **Terminal Errors (Linux)**: Do not add complex `QGraphicsEffects` (Shadow/Opacity) to the Splash Window. They cause "Painter not active" errors on some Linux compositors.
-   **Immediate Close**: Removing the time check in `show_and_close_splash` will make the app feel "glitchy" on fast machines.
