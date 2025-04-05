<p align="center">
  <img src="https://raw.githubusercontent.com/tomofberlin/rapidinstall/master/Bolt.png" alt="Bolt the Builder Bot - RapidInstall Mascot" width="200">
</p>

# rapidinstall

[![PyPI version](https://badge.fury.io/py/rapidinstall.svg)](https://badge.fury.io/py/rapidinstall) <!-- Placeholder: Update link/badge if you publish to PyPI -->
<!-- --- CHANGE THIS BADGE --- -->
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) <!-- Changed from MIT -->
<!-- ------------------------ 
[![GitHub Repo stars](https://img.shields.io/github/stars/tomOfBerlin/rapidinstall?style=social)](https://github.com/tomOfBerlin/rapidinstall)
-->
A simple Python utility to run multiple shell command sequences (e.g., complex installations, downloads, build steps) in parallel, providing status updates and aggregated output directly to the console.

## Features

*   **Parallel Execution:** Runs multiple tasks concurrently using `subprocess`.
*   **Real-time Output:** Captures stdout and stderr from tasks.
*   **Status Updates:** Periodically shows which tasks are still running and recent output.
*   **Clear Formatting:** Presents startup, status, and completion information in distinct blocks.
*   **Simple API:** Easy to integrate into existing Python scripts.
*   **Pure Python:** Relies only on the standard library.

## Installation

```bash
pip install rapidinstall
```

### Example: first look
```python
import rapidinstall

my_tasks = [
    {'name': 'Pip', 'commands': 'pip install this that'},
    {'name': 'Download MyFile', 'commands': "wget https://my.file/is_here"}
]

rapidinstall.install(my_tasks)
```
Downloads and Installs in paralell and updates you on the progress


### Example: typical
```python
import rapidinstall

clone_and_install = '''clone https://github.com/tomOfBerlin/rapidinstall
cd rapidinstall
python setup.py install
cd ..'''

my_tasks = [
    {'name': 'Pip', 'commands': 'pip install this that'},
    {'name': 'Download MyFile', 'commands': "wget https://my.file/is_here"},
	{'name': 'Clone and install Dependencies', 'commands': clone_and_install}
]

rapidinstall.install(my_tasks)
```
You can execute commands sequentially, great for git installs.


### Example: silent

```python
# Completely silent - verbose is turned on by default
rapidinstall.install(my_tasks, verbose=False)

# Updates every 60 seconds
rapidinstall.install(my_tasks, update_interval=60)
```

### Example: advanced
```python
# Import directly from the run module (previously executor)
from rapidinstall.run import run_tasks
# You can also access constants like:
# from rapidinstall.run import DEFAULT_STATUS_UPDATE_INTERVAL

task_a = {'name': 'Task A', 'commands': 'echo "Executing A"; sleep 1'}
task_b = {'name': 'Task B', 'commands': 'echo "Executing B"; sleep 1'}

print("\n--- Starting Advanced Example (run_tasks) ---")
# Pass arguments directly to run_tasks
results_advanced = run_tasks(todos=[task_a, task_b], verbose=True, update_interval=10)
print("--- Advanced Example Finished ---")

print("\n--- Task Execution Summary (Advanced) ---")
print(results_advanced) # Print the raw results dictionary
```
