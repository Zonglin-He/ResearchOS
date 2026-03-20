from pathlib import Path

from app.tools.filesystem import FilesystemTool
from app.tools.python_exec import PythonExecTool
from app.tools.shell_tool import ShellTool


def test_filesystem_tool_read_write_and_list(tmp_path: Path) -> None:
    import asyncio

    tool = FilesystemTool()
    target = tmp_path / "note.txt"

    asyncio.run(tool.execute(action="write_text", path=str(target), content="hello"))
    read_result = asyncio.run(tool.execute(action="read_text", path=str(target)))
    list_result = asyncio.run(tool.execute(action="list_dir", path=str(tmp_path)))

    assert read_result["content"] == "hello"
    assert str(target) in list_result["items"]


def test_shell_tool_executes_command() -> None:
    import asyncio

    result = asyncio.run(ShellTool().execute(command="python -c \"print('ok')\""))

    assert result["returncode"] == 0
    assert result["stdout"].strip() == "ok"


def test_python_exec_tool_executes_code() -> None:
    import asyncio

    result = asyncio.run(PythonExecTool().execute(code="print('hello')"))

    assert result["returncode"] == 0
    assert result["stdout"].strip() == "hello"
