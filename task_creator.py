from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageGrab, ImageOps, ImageTk, UnidentifiedImageError


APP_TITLE = "AI Task Creator"
IMAGE_TYPES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
TASK_PATTERN = re.compile(r"^task_(\d+)$", re.IGNORECASE)
TASK_IMAGE_PATTERN = re.compile(r"^image_(\d+)(\.[^.]+)$", re.IGNORECASE)
QUEUE_DIR_NAMES = ("todo", "done")
SETTINGS_DIR = Path(os.getenv("APPDATA") or Path.home()) / "AI Task Creator"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class TaskImage:
    source_path: Path | None = None
    image: Image.Image | None = None
    label: str = "Afbeelding"

    @classmethod
    def from_path(cls, path: Path) -> "TaskImage":
        return cls(source_path=path, label=path.name)

    @classmethod
    def from_clipboard(cls, image: Image.Image) -> "TaskImage":
        return cls(image=image.copy(), label="Geplakte afbeelding")


def task_collections(project_dir: Path) -> list[tuple[str, Path]]:
    """Return the task directories exposed by a selected project location."""
    if project_dir.is_dir():
        try:
            children = {
                child.name.lower(): child
                for child in project_dir.iterdir()
                if child.is_dir()
            }
        except OSError:
            children = {}
        queue_dirs = [
            (name, children[name])
            for name in QUEUE_DIR_NAMES
            if name in children
        ]
        if queue_dirs:
            return queue_dirs
    return [(project_dir.name or "tasks", project_dir)]


def task_save_directory(project_dir: Path) -> Path:
    """Choose where newly-created tasks belong for this project."""
    collections = task_collections(project_dir)
    if any(name in QUEUE_DIR_NAMES for name, _path in collections):
        for name, path in collections:
            if name == "todo":
                return path
        return project_dir / "todo"
    return project_dir


def next_task_number(project_dir: Path) -> int:
    """Return one more than the highest task number in all visible groups."""
    highest = 0
    for _name, collection_dir in task_collections(project_dir):
        if not collection_dir.is_dir():
            continue
        try:
            children = collection_dir.iterdir()
            for child in children:
                if not child.is_dir():
                    continue
                match = TASK_PATTERN.fullmatch(child.name)
                if match:
                    highest = max(highest, int(match.group(1)))
        except OSError:
            continue
    return highest + 1


def save_task(
    project_dir: Path,
    text: str,
    images: list[TaskImage],
    existing_dir: Path | None = None,
) -> Path:
    """Create or safely replace a task through a temporary directory."""
    project_dir.mkdir(parents=True, exist_ok=True)
    project_dir = project_dir.resolve()

    if existing_dir is None:
        task_number = next_task_number(project_dir)
        task_name = f"task_{task_number:03d}"
        target_dir = task_save_directory(project_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_dir = target_dir.resolve()
        final_dir = target_dir / task_name
    else:
        final_dir = existing_dir.resolve()
        allowed_parents = {
            path.resolve()
            for _name, path in task_collections(project_dir)
            if path.is_dir()
        }
        if final_dir.parent not in allowed_parents or not TASK_PATTERN.fullmatch(final_dir.name):
            raise ValueError("De bestaande taak staat niet in een geldige taakmap.")
        if not final_dir.is_dir():
            raise FileNotFoundError(f"De taakmap bestaat niet meer: {final_dir}")
        task_name = final_dir.name
        target_dir = final_dir.parent

    temp_dir = Path(tempfile.mkdtemp(prefix=f".{task_name}-", dir=target_dir))
    backup_dir: Path | None = None

    try:
        (temp_dir / "task.txt").write_text(text, encoding="utf-8")
        for index, item in enumerate(images, start=1):
            if item.source_path is not None:
                suffix = item.source_path.suffix.lower() or ".png"
                shutil.copy2(item.source_path, temp_dir / f"image_{index}{suffix}")
            elif item.image is not None:
                item.image.save(temp_dir / f"image_{index}.png", format="PNG")
            else:
                raise ValueError(f"Afbeelding {index} heeft geen geldige bron.")
        if existing_dir is not None:
            backup_dir = target_dir / f".{task_name}.backup-{uuid.uuid4().hex}"
            final_dir.rename(backup_dir)
        try:
            temp_dir.rename(final_dir)
        except Exception:
            if backup_dir is not None and backup_dir.exists() and not final_dir.exists():
                backup_dir.rename(final_dir)
            raise
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    finally:
        if backup_dir is not None and final_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    return final_dir


class ScrollableImageGrid(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#f3f4f6")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, background="#f3f4f6")
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.content.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_width)

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)


class TaskCreatorApp:
    THUMBNAIL_SIZE = (190, 125)

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1120x720")
        self.root.minsize(820, 560)

        self.images: list[TaskImage] = []
        self.thumbnail_refs: list[ImageTk.PhotoImage] = []
        self.project_var = tk.StringVar(value=self._load_last_project())
        self.status_var = tk.StringVar(value="Klaar")
        self.mode_var = tk.StringVar(value="Nieuwe taak")
        self.save_label_var = tk.StringVar(value="Save new")
        self.task_paths: list[Path] = []
        self.task_tree_paths: dict[str, Path] = {}
        self.selected_task: Path | None = None
        self.active_project = self.project_var.get().strip()
        self.dirty = False
        self.loading = False
        self.suppress_task_selection = False

        self._configure_style()
        self._build_ui()
        self._bind_shortcuts()
        self._render_grid()
        self.refresh_tasks()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _load_last_project() -> str:
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            project = settings.get("last_project", "")
            return project if isinstance(project, str) else ""
        except (OSError, json.JSONDecodeError):
            return ""

    def _remember_project(self) -> None:
        project = self.project_var.get().strip()
        if not project:
            return
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            temporary = SETTINGS_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"last_project": project}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(SETTINGS_FILE)
        except OSError:
            # Remembering the location is convenient but should never block work.
            pass

    def _close(self) -> None:
        self._remember_project()
        self.root.destroy()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Hint.TLabel", foreground="#5f6368")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)

        sidebar = ttk.Frame(panes, width=190, padding=(0, 0, 14, 0))
        main = ttk.Frame(panes, padding=(14, 0, 0, 0))
        panes.add(sidebar, weight=0)
        panes.add(main, weight=1)

        ttk.Label(sidebar, text="Tasks", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        list_frame = ttk.Frame(sidebar)
        list_frame.pack(fill="both", expand=True)
        self.task_tree = ttk.Treeview(
            list_frame,
            show="tree",
            selectmode="browse",
            height=20,
        )
        task_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=task_scrollbar.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        task_scrollbar.pack(side="right", fill="y")
        ttk.Button(sidebar, text="Refresh", command=self.refresh_tasks).pack(fill="x", pady=(10, 0))

        top_row = ttk.Frame(main)
        top_row.pack(fill="x", pady=(0, 10))
        ttk.Label(top_row, text="Afbeeldingen", style="Title.TLabel").pack(side="left")
        ttk.Label(
            top_row,
            text="Plak met Ctrl+V of kies bestanden",
            style="Hint.TLabel",
        ).pack(side="left", padx=(14, 0), pady=(6, 0))
        ttk.Button(top_row, text="+ Afbeeldingen", command=self.add_files).pack(side="right")
        ttk.Label(top_row, textvariable=self.mode_var, style="Hint.TLabel").pack(
            side="right", padx=(0, 14), pady=(6, 0)
        )

        self.grid = ScrollableImageGrid(main)
        self.grid.pack(fill="both", expand=True, pady=(0, 16))
        self.grid.canvas.bind("<Double-Button-1>", lambda _event: self.add_files())

        lower = ttk.Frame(main)
        lower.pack(fill="both")

        location_row = ttk.Frame(lower)
        location_row.pack(fill="x", pady=(0, 10))
        ttk.Label(location_row, text="Projectlocatie:").pack(side="left")
        self.location_entry = ttk.Entry(location_row, textvariable=self.project_var)
        self.location_entry.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(location_row, text="Bladeren…", command=self.browse_project).pack(side="right")

        ttk.Label(lower, text="Taaktekst:").pack(anchor="w", pady=(0, 5))
        self.text = tk.Text(
            lower,
            height=9,
            wrap="word",
            undo=True,
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
            padx=9,
            pady=8,
        )
        self.text.pack(fill="both", expand=True)

        button_row = ttk.Frame(lower)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Label(button_row, textvariable=self.status_var, style="Hint.TLabel").pack(side="left")
        ttk.Button(button_row, text="New", command=self.new_task).pack(side="right", padx=(8, 0))
        self.save_button = ttk.Button(
            button_row,
            textvariable=self.save_label_var,
            command=self.save,
            style="Primary.TButton",
        )
        self.save_button.pack(side="right")
        self.save_as_button = ttk.Button(
            button_row,
            text="Save as new",
            command=self.save_as_new,
            state="disabled",
        )
        self.save_as_button.pack(side="right", padx=(0, 8))

    def _bind_shortcuts(self) -> None:
        # Widget bindings run before Tk's standard Text/Entry bindings. This lets
        # image clipboard content go to the grid while ordinary text still pastes.
        self.text.bind("<Control-v>", self.handle_paste)
        self.location_entry.bind("<Control-v>", self.handle_paste)
        self.root.bind_all("<Control-v>", self.handle_paste, add="+")
        self.root.bind("<Control-s>", lambda _event: self.save())
        self.root.bind("<Control-n>", lambda _event: self.new_task())
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.location_entry.bind("<Return>", self._apply_project_location)
        self.location_entry.bind("<FocusOut>", self._apply_project_location)
        self.task_tree.bind("<<TreeviewSelect>>", self._on_task_selected)

    def _mark_dirty(self) -> None:
        if self.loading:
            return
        self.dirty = True
        if self.selected_task is not None:
            self.mode_var.set(f"{self.selected_task.name} • gewijzigd")

    def _on_text_modified(self, _event: tk.Event) -> None:
        if self.text.edit_modified():
            self._mark_dirty()
            self.text.edit_modified(False)

    def _apply_project_location(self, _event: tk.Event | None = None) -> str | None:
        new_project = self.project_var.get().strip()
        if new_project == self.active_project:
            self.refresh_tasks()
            return "break" if _event and _event.type == tk.EventType.KeyPress else None

        if self.selected_task is not None and self.dirty:
            if not messagebox.askyesno(
                "Niet-opgeslagen wijzigingen",
                "Project wisselen en de wijzigingen aan de geopende taak negeren?",
            ):
                self.project_var.set(self.active_project)
                return "break" if _event and _event.type == tk.EventType.KeyPress else None

        if self.selected_task is not None:
            self._clear_editor()

        self.active_project = new_project
        self.selected_task = None
        self._update_mode()
        self._remember_project()
        self.refresh_tasks()
        return "break" if _event and _event.type == tk.EventType.KeyPress else None

    def refresh_tasks(self) -> None:
        selected = self.selected_task
        self.task_paths = []
        self.task_tree_paths = {}

        self.suppress_task_selection = True
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)

        project_text = self.active_project.strip()
        if project_text:
            project_dir = Path(project_text).expanduser()
            if project_dir.is_dir():
                collections = task_collections(project_dir)
                grouped = len(collections) > 1 or collections[0][0] in QUEUE_DIR_NAMES
                for group_index, (name, collection_dir) in enumerate(collections):
                    parent = ""
                    if grouped:
                        parent = f"group:{group_index}"
                        self.task_tree.insert("", "end", iid=parent, text=name, open=True)
                    candidates: list[tuple[int, Path]] = []
                    try:
                        for child in collection_dir.iterdir():
                            match = TASK_PATTERN.fullmatch(child.name)
                            if match and child.is_dir():
                                candidates.append((int(match.group(1)), child.resolve()))
                    except OSError:
                        candidates = []
                    candidates.sort(key=lambda item: item[0], reverse=True)
                    for _number, path in candidates:
                        item_id = f"task:{len(self.task_paths)}"
                        self.task_paths.append(path)
                        self.task_tree_paths[item_id] = path
                        self.task_tree.insert(parent, "end", iid=item_id, text=path.name)
                        if path == selected:
                            self.task_tree.selection_set(item_id)
                            self.task_tree.see(item_id)
        self.suppress_task_selection = False

    def _on_task_selected(self, _event: tk.Event) -> None:
        if self.suppress_task_selection:
            return
        selection = self.task_tree.selection()
        if not selection:
            return
        target = self.task_tree_paths.get(selection[0])
        if target is None:
            return
        if target == self.selected_task:
            return

        if self.dirty and not messagebox.askyesno(
            "Niet-opgeslagen wijzigingen",
            "Andere taak openen en de huidige wijzigingen negeren?",
        ):
            self._restore_task_selection()
            return

        self._load_task(target)

    def _restore_task_selection(self) -> None:
        self.suppress_task_selection = True
        self.task_tree.selection_set(())
        if self.selected_task is not None:
            for item_id, path in self.task_tree_paths.items():
                if path == self.selected_task:
                    self.task_tree.selection_set(item_id)
                    self.task_tree.see(item_id)
                    break
        self.suppress_task_selection = False

    def _load_task(self, task_dir: Path) -> None:
        try:
            text_file = task_dir / "task.txt"
            task_text = text_file.read_text(encoding="utf-8") if text_file.is_file() else ""
            image_files: list[tuple[int, Path]] = []
            for child in task_dir.iterdir():
                match = TASK_IMAGE_PATTERN.fullmatch(child.name)
                if (
                    match
                    and child.is_file()
                    and child.suffix.lower() in IMAGE_TYPES
                ):
                    image_files.append((int(match.group(1)), child.resolve()))
            image_files.sort(key=lambda item: item[0])
        except OSError as error:
            messagebox.showerror("Taak openen mislukt", f"De taak kon niet worden geopend:\n\n{error}")
            self._restore_task_selection()
            return

        self.loading = True
        self.images = [TaskImage.from_path(path) for _number, path in image_files]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", task_text)
        self.text.edit_modified(False)
        self.selected_task = task_dir
        self.dirty = False
        self.loading = False
        self._render_grid()
        self._update_mode()
        self.status_var.set(f"Geopend: {task_dir.name}")

    def _update_mode(self) -> None:
        if self.selected_task is None:
            self.mode_var.set("Nieuwe taak")
            self.save_label_var.set("Save new")
            self.save_as_button.configure(state="disabled")
        else:
            self.mode_var.set(self.selected_task.name)
            self.save_label_var.set(f"Update {self.selected_task.name}")
            self.save_as_button.configure(state="normal")

    def browse_project(self) -> None:
        selected = filedialog.askdirectory(
            title="Kies een projectlocatie",
            initialdir=self.project_var.get() or None,
        )
        if selected:
            self.project_var.set(selected)
            self._apply_project_location()

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Kies afbeeldingen",
            filetypes=[
                ("Afbeeldingen", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                ("Alle bestanden", "*.*"),
            ],
        )
        if paths:
            self._add_paths([Path(path) for path in paths])

    def _add_paths(self, paths: list[Path]) -> int:
        added = 0
        invalid: list[str] = []
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in IMAGE_TYPES:
                invalid.append(path.name)
                continue
            try:
                with Image.open(path) as candidate:
                    candidate.verify()
            except (OSError, UnidentifiedImageError):
                invalid.append(path.name)
                continue
            self.images.append(TaskImage.from_path(path.resolve()))
            added += 1

        if added:
            self._render_grid()
            self._mark_dirty()
            self.status_var.set(f"{added} afbeelding(en) toegevoegd")
        if invalid:
            messagebox.showwarning(
                "Niet toegevoegd",
                "Deze bestanden zijn geen ondersteunde afbeeldingen:\n\n" + "\n".join(invalid),
            )
        return added

    def handle_paste(self, event: tk.Event) -> str | None:
        try:
            clipboard = ImageGrab.grabclipboard()
        except (OSError, NotImplementedError):
            return None

        if isinstance(clipboard, Image.Image):
            self.images.append(TaskImage.from_clipboard(clipboard))
            self._render_grid()
            self._mark_dirty()
            self.status_var.set("Afbeelding van klembord toegevoegd")
            return "break"

        if isinstance(clipboard, list):
            paths = [Path(item) for item in clipboard if isinstance(item, (str, os.PathLike))]
            if self._add_paths(paths):
                return "break"

        # Returning None preserves normal text paste in Text and Entry widgets.
        return None

    def _load_preview(self, item: TaskImage) -> Image.Image:
        if item.source_path is not None:
            with Image.open(item.source_path) as source:
                preview = ImageOps.exif_transpose(source).convert("RGB")
        elif item.image is not None:
            preview = ImageOps.exif_transpose(item.image).convert("RGB")
        else:
            raise ValueError("Afbeelding heeft geen bron.")

        preview.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        background = Image.new("RGB", self.THUMBNAIL_SIZE, "white")
        x = (self.THUMBNAIL_SIZE[0] - preview.width) // 2
        y = (self.THUMBNAIL_SIZE[1] - preview.height) // 2
        background.paste(preview, (x, y))
        return background

    def _render_grid(self) -> None:
        for widget in self.grid.content.winfo_children():
            widget.destroy()
        self.thumbnail_refs.clear()

        if not self.images:
            empty = tk.Frame(self.grid.content, background="#f3f4f6")
            empty.pack(fill="both", expand=True, pady=55)
            tk.Label(
                empty,
                text="Nog geen afbeeldingen",
                background="#f3f4f6",
                foreground="#6b7280",
                font=("Segoe UI", 12, "bold"),
            ).pack()
            tk.Label(
                empty,
                text="Ctrl+V, dubbelklik of gebruik ‘+ Afbeeldingen’",
                background="#f3f4f6",
                foreground="#6b7280",
                font=("Segoe UI", 9),
            ).pack(pady=(5, 0))
            return

        available_width = max(self.grid.canvas.winfo_width(), 660)
        columns = max(1, available_width // 225)
        for column in range(columns):
            self.grid.content.grid_columnconfigure(column, weight=1)

        for index, item in enumerate(self.images):
            card = tk.Frame(
                self.grid.content,
                background="white",
                highlightbackground="#d1d5db",
                highlightthickness=1,
                padx=8,
                pady=8,
            )
            card.grid(row=index // columns, column=index % columns, padx=7, pady=7, sticky="n")

            try:
                photo = ImageTk.PhotoImage(self._load_preview(item))
                self.thumbnail_refs.append(photo)
                tk.Label(card, image=photo, background="white").pack()
            except (OSError, ValueError):
                tk.Label(
                    card,
                    text="Preview niet beschikbaar",
                    width=26,
                    height=7,
                    background="white",
                    foreground="#b91c1c",
                ).pack()

            tk.Label(
                card,
                text=item.label,
                background="white",
                foreground="#374151",
                width=25,
                anchor="w",
            ).pack(pady=(6, 0))

            close = tk.Button(
                card,
                text="×",
                command=self._remove_callback(index),
                font=("Segoe UI", 11, "bold"),
                foreground="white",
                background="#dc2626",
                activebackground="#b91c1c",
                activeforeground="white",
                relief="flat",
                borderwidth=0,
                cursor="hand2",
                width=2,
            )
            close.place(relx=1.0, x=-7, y=7, anchor="ne")

    def _remove_callback(self, index: int) -> Callable[[], None]:
        def remove() -> None:
            del self.images[index]
            self._render_grid()
            self._mark_dirty()
            self.status_var.set("Afbeelding verwijderd")

        return remove

    def _clear_editor(self) -> None:
        self.loading = True
        self.images.clear()
        self.text.delete("1.0", "end")
        self.text.edit_modified(False)
        self.dirty = False
        self.loading = False
        self._render_grid()

    def new_task(self) -> None:
        if self.dirty and not messagebox.askyesno(
            "Nieuwe taak",
            "Niet-opgeslagen wijzigingen negeren en een nieuwe taak beginnen?",
        ):
            return
        self._clear_editor()
        self.selected_task = None
        self.suppress_task_selection = True
        self.task_tree.selection_set(())
        self.suppress_task_selection = False
        self._update_mode()
        self.status_var.set("Nieuwe lege taak")
        self.text.focus_set()

    def save(self) -> None:
        self._save(as_new=False)

    def save_as_new(self) -> None:
        self._save(as_new=True)

    def _save(self, as_new: bool) -> None:
        if self.project_var.get().strip() != self.active_project:
            self._apply_project_location()
        raw_project = self.project_var.get().strip()
        if not raw_project:
            messagebox.showwarning("Projectlocatie ontbreekt", "Kies eerst een projectlocatie.")
            self.browse_project()
            return

        project_dir = Path(raw_project).expanduser()
        if project_dir.exists() and not project_dir.is_dir():
            messagebox.showerror("Ongeldige locatie", "De projectlocatie is geen map.")
            return

        text = self.text.get("1.0", "end-1c")
        if not text.strip() and not self.images:
            messagebox.showwarning(
                "Lege taak",
                "Voeg minimaal tekst of een afbeelding toe voordat je opslaat.",
            )
            return

        try:
            existing = None if as_new else self.selected_task
            saved_dir = save_task(project_dir, text, self.images, existing_dir=existing)
        except Exception as error:
            messagebox.showerror("Opslaan mislukt", f"De taak kon niet worden opgeslagen:\n\n{error}")
            return

        self.active_project = str(project_dir)
        self.project_var.set(str(project_dir))
        self.selected_task = saved_dir
        self.dirty = False
        self._remember_project()
        self.refresh_tasks()
        self._restore_task_selection()
        self._load_task(saved_dir)
        self.status_var.set(f"Opgeslagen: {saved_dir.name}")


def main() -> None:
    root = tk.Tk()
    TaskCreatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
