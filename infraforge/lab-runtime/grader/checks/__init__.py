from grader.checks.shell_check import ShellCheck
from grader.checks.http_check import HttpCheck
from grader.checks.process_check import ProcessCheck
from grader.checks.file_check import FileCheck

CHECK_REGISTRY = {
    "shell": ShellCheck,
    "http": HttpCheck,
    "process": ProcessCheck,
    "file": FileCheck,
}

__all__ = ["CHECK_REGISTRY", "ShellCheck", "HttpCheck", "ProcessCheck", "FileCheck"]
