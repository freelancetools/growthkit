"""Provides functions for executing shell commands with different output handling."""
import inspect
import subprocess
from growthkit.utils.style import ansi
from growthkit.utils.logs import report

def execute(command):
    """
    - Run a command and return the output and error
    - The command's output and error streams are connected to pipes.
    - Output is not displayed in real-time; it's collected and
    can be processed after the command finishes.
    - This means that the command will not block the parent process.
    - This is useful for commands that need to be run in the background,
    such as long-running commands.
    """
    # Get the caller's module name
    caller_frame = inspect.currentframe().f_back
    caller_module = inspect.getmodule(caller_frame)
    logger = report.settings(caller_module.__file__)

    logger.info("Executing command: %s", command)
    print(f"{ansi.grey}{command}{ansi.reset}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output_bytes, error_bytes = process.communicate()

    output = output_bytes.decode('utf-8').strip()
    error = error_bytes.decode('utf-8').strip()

    if output:
        logger.info(output)
        print(f"{ansi.cyan}> {ansi.reset}{output}\n")
    if error:
        logger.error(error)
        print(f"{ansi.red}> {ansi.reset}{error}\n")
    return {"output": output, "error": error}


def run(command):
    """
    - Run a command and return the output and error
    - The command's output and error streams are connected directly to the parent process's streams.
    - Output is displayed in real-time as the command executes.
    - This means that the command will block the parent process until it finishes.
    - This is useful for commands that need to be run in the foreground,
    such as interactive commands.
    - The function allows for interactive use, where the user can see and
    potentially respond to output as it's generated.
    """
    # Get the caller's module name
    caller_frame = inspect.currentframe().f_back
    caller_module = inspect.getmodule(caller_frame)
    logger = report.settings(caller_module.__file__)

    logger.info("Executing command: %s", command)
    print(f"{ansi.grey}{command}{ansi.reset}")
    process = subprocess.Popen(command, shell=True)
    output_bytes, error_bytes = process.communicate()

    output = output_bytes.decode('utf-8').strip() if output_bytes else ""
    error = error_bytes.decode('utf-8').strip() if error_bytes else ""

    if output:
        logger.info(output)
        print(f"{ansi.cyan}> {ansi.reset}{output}\n")
    if error:
        logger.error(error)
        print(f"{ansi.red}> {ansi.reset}{error}\n")
    return {"output": output, "error": error}
