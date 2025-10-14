import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kimi_coding_agent_v_6_1 import (
    FileItem,
    FileMap,
    list_directory_impl,
    read_text_file_impl,
    write_many_impl,
    write_text_file_impl,
)


def test_file_item_normalizes_iterable_content():
    item = FileItem.model_validate({"path": "README.md", "content": ["Hello", "World"]})
    assert item.content == "Hello\nWorld"


def test_file_map_accepts_plain_dict():
    fm = FileMap.model_validate({"app.py": {"text": "print('hi')"}})
    assert len(fm.files) == 1
    assert fm.files[0].path == "app.py"
    assert fm.files[0].content == "print('hi')"


def test_write_text_file_impl_supports_nested_directories(tmp_path: Path):
    result = write_text_file_impl(tmp_path, "src/app.tsx", ["const answer = 42", "export default answer"])
    assert result["ok"] is True
    written = (tmp_path / "src/app.tsx").read_text()
    assert written == "const answer = 42\nexport default answer"


def test_write_many_impl_reports_failure(tmp_path: Path):
    target = tmp_path / "data.json"
    target.write_text(json.dumps({"a": 1}))
    fm = FileMap.model_validate([
        {"path": "data.json", "content": json.dumps({"a": 2})},
    ])
    result = write_many_impl(tmp_path, fm, overwrite=False)
    assert result["ok"] is False
    assert result["results"]["data.json"]["ok"] is False


def test_read_text_file_impl_returns_content(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("hello world")
    result = read_text_file_impl(tmp_path, "notes.txt")
    assert result["ok"] is True
    assert result["content"] == "hello world"


def test_list_directory_impl_lists_entries(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b.txt").write_text("b")
    result = list_directory_impl(tmp_path, ".")
    assert result["ok"] is True
    names = {entry["name"] for entry in result["entries"]}
    assert names == {"a", "b.txt"}
    directory_info = next(entry for entry in result["entries"] if entry["name"] == "a")
    assert directory_info["is_dir"] is True
    assert directory_info["is_file"] is False
