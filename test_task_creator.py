from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from task_creator import (
    decode_macos_clipboard_data,
    next_task_number,
    save_task,
    task_collections,
)


class TaskStorageTests(unittest.TestCase):
    def test_decodes_macos_osascript_image_data(self) -> None:
        self.assertEqual(
            decode_macos_clipboard_data("«data TIFF48656c6c6f»\n".encode("utf-8"), "TIFF"),
            b"Hello",
        )

    def test_queue_root_exposes_todo_and_done(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "todo" / "task_006").mkdir(parents=True)
            (root / "done" / "task_015").mkdir(parents=True)

            self.assertEqual(
                [(name, path.relative_to(root)) for name, path in task_collections(root)],
                [("todo", Path("todo")), ("done", Path("done"))],
            )
            self.assertEqual(next_task_number(root), 16)

    def test_new_queue_task_is_saved_to_todo(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "todo" / "task_002").mkdir(parents=True)
            (root / "done" / "task_008").mkdir(parents=True)

            saved = save_task(root, "Nieuwe taak", [])

            self.assertEqual(saved, root.resolve() / "todo" / "task_009")
            self.assertEqual((saved / "task.txt").read_text(encoding="utf-8"), "Nieuwe taak")

    def test_updating_done_task_keeps_it_in_done(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "done" / "task_004"
            task.mkdir(parents=True)
            (root / "todo").mkdir()
            (task / "task.txt").write_text("Oud", encoding="utf-8")

            saved = save_task(root, "Bijgewerkt", [], existing_dir=task)

            self.assertEqual(saved, task.resolve())
            self.assertEqual((task / "task.txt").read_text(encoding="utf-8"), "Bijgewerkt")

    def test_legacy_flat_project_still_saves_directly(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "task_003").mkdir()

            saved = save_task(root, "Taak", [])

            self.assertEqual(saved, root.resolve() / "task_004")

    def test_suffix_task_names_are_counted_for_next_number(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "task_021_gpu_text_phase_0").mkdir()
            (root / "task_022_gpu_text_canonical_layer").mkdir()
            (root / "task_024_gpu_text_font_registry").mkdir()

            self.assertEqual(next_task_number(root), 25)

    def test_updating_suffix_task_name_is_allowed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "todo" / "task_021_gpu_text_phase_0"
            task.mkdir(parents=True)
            (root / "done").mkdir()
            (task / "task.txt").write_text("Oud", encoding="utf-8")

            saved = save_task(root, "Bijgewerkt", [], existing_dir=task)

            self.assertEqual(saved, task.resolve())
            self.assertEqual((task / "task.txt").read_text(encoding="utf-8"), "Bijgewerkt")


if __name__ == "__main__":
    unittest.main()
