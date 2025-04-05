# rapidinstall/__init__.py

# Import the core function from the module 'run.py'
from ...old.__run import run_tasks
# Import the 'run' module itself to make its default constants accessible if needed
from ...old import __run # Reference to the run module

# Define the public API - the install function
# This function should be directly accessible after 'import rapidinstall'
def install(todos, update_interval=None, verbose=True):
    """
    Runs a list of installation tasks (shell commands) in parallel.

    Provides real-time status updates and aggregated output. See run_tasks
    for more detailed argument descriptions.

    Example:
        import rapidinstall
        my_tasks = [
            {'name': 'task1', 'commands': 'echo "Hello"; sleep 2'},
            {'name': 'task2', 'commands': 'echo "World"; sleep 1'}
        ]
        results = rapidinstall.install(my_tasks)
        print(results)

    Args:
        todos: List of task dictionaries [{'name': str, 'commands': str}, ...].
        update_interval (Optional[int]): Print status every N iterations.
                                         Defaults to run.DEFAULT_STATUS_UPDATE_INTERVAL.
                                         Set to 0 or None to disable.
        verbose (bool): Print progress and output to console. Defaults to True.

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary mapping task names to results
                                   (stdout, stderr, returncode, pid).
    """
    # Use default from run module if not provided, access via the imported 'run' module
    interval_to_use = update_interval if update_interval is not None else __run.DEFAULT_STATUS_UPDATE_INTERVAL

    # Call the core function imported from run.py
    return run_tasks(todos=todos, update_interval=interval_to_use, verbose=verbose)

# Package version (consider using importlib.metadata for complex cases)
__version__ = "0.9.0" # Update as needed

# Optionally define __all__ to control `from rapidinstall import *`
# This explicitly lists what is imported with '*'
# Even without __all__, 'install' should be accessible via standard import
__all__ = ['install', 'run_tasks', '__run']