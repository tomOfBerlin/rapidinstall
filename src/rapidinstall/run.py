# rapidinstall/run.py

import subprocess
import time
import threading
import queue
import os
import sys
from typing import List, Dict, Any, Tuple, Optional
import re

# --- Configuration --- (Can be overridden by function args)
DEFAULT_STATUS_UPDATE_INTERVAL = 30  # Check every 30 iterations (~15 seconds)
SEPARATOR = "*" * 60
ANSI_ESCAPE_REGEX = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])') # <<< ADDED

# --- Helper Functions ---

def _print_locked(lock: threading.Lock, *args, **kwargs):
    """Prints output protected by a lock."""
    with lock:
        print(*args, **kwargs)

def _strip_ansi(text: str) -> str: # <<< ADDED
    """Removes ANSI escape sequences from a string."""
    return ANSI_ESCAPE_REGEX.sub('', text)

def _format_output_block(title: str, content: str) -> str:
    """Formats a block of output with separators."""
    if not content.strip():
        return ""
    return f"{SEPARATOR}\n{title}\n{SEPARATOR}\n{content.strip()}\n{SEPARATOR}\n"

def _process_status_lines(lines: List[str]) -> str: # <<< ADDED
    """Processes lines for status updates: handles \r and strips ANSI."""
    processed_output = ""
    current_line = ""
    for raw_line in lines:
        # Strip ANSI codes first
        stripped_line = _strip_ansi(raw_line)

        # Handle carriage returns within the stripped line
        parts = stripped_line.split('\r')
        if len(parts) > 1:
            # If \r exists, the last part overwrites the current_line buffer
            current_line = parts[-1]
        else:
            # No \r, append to buffer (if it wasn't just overwritten)
            current_line += parts[0]

        # If the raw line ended with a newline, finalize the current_line
        # and add it to the output, then reset buffer.
        if raw_line.endswith('\n'):
            processed_output += current_line # Add completed line
            current_line = "" # Reset for next line

    # Add any remaining content in the buffer (if the last line didn't end with \n)
    if current_line:
        processed_output += current_line

    # Ensure final newline if original lines ended with one
    if lines and lines[-1].endswith('\n') and not processed_output.endswith('\n'):
        processed_output += '\n'

    return processed_output.strip() # Return stripped final content

# --- Thread Function to Read Stream ---
def _stream_reader(stream, output_queue: queue.Queue, stream_name: str):
    """Reads lines from a stream and puts them onto the output queue."""
    try:
        # Use iter(stream.readline, '') which is efficient for text streams
        for line in iter(stream.readline, ''):
            if line: # Only put non-empty lines
                output_queue.put((stream_name, line))
            else: # End of stream detected by empty string
                break
    except ValueError:
        # Can happen if the stream is closed unexpectedly
        pass
    except Exception as e:
        # Try to report the error back through the queue
        error_line = f"*** Exception in _stream_reader ({stream_name}): {e} ***\n"
        try:
            output_queue.put(('stderr', error_line))
        except Exception:
            # Fallback if queue itself is broken
            print(error_line, file=sys.stderr)
    finally:
        # Ensure the stream is closed from this end (optional but good practice)
        try:
            stream.close()
        except Exception:
            pass
        # Signal that this reader thread is finished using a sentinel
        try:
            output_queue.put((stream_name, None))
        except Exception:
            # If putting the sentinel fails, the main loop's join/timeout
            # will have to handle recognizing thread completion.
            pass

# --- Core Execution Logic ---
def run_tasks(
    todos: List[Dict[str, str]],
    update_interval: int = DEFAULT_STATUS_UPDATE_INTERVAL,
    verbose: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Runs a list of tasks (shell commands) in parallel, monitors them,
    and optionally prints status updates and final output.

    Args:
        todos: A list of dictionaries, where each dictionary must have
               'name' (str) and 'commands' (str - potentially multi-line
               shell script).
        update_interval: Print status update every N monitoring iterations.
                         Set to 0 or None to disable periodic updates.
        verbose: If True, print startup, status, and completion messages
                 to stdout. If False, run silently (except for script errors).

    Returns:
        A dictionary mapping task names to their results:
        {
            'task_name': {
                'stdout': str,
                'stderr': str,
                'returncode': int,
                'pid': int | None # PID if successfully started
            },
            ...
        }
    """
    script_start_time = time.time()
    print_lock = threading.Lock() # Lock for console output if verbose

    # Stores {'process_obj': {'name': str, 'output_queue': Queue, ...}}
    active_processes: Dict[subprocess.Popen, Dict[str, Any]] = {}
    # Stores final results: {name: {'stdout': str, 'stderr': str, ...}}
    final_results: Dict[str, Dict[str, Any]] = {}
    # Store launch details for initial summary (if verbose)
    process_launch_details = []

    #if verbose:
    #    _print_locked(print_lock, "Starting background processes...")

    for todo in todos:
        name = todo.get('name')
        commands_script = todo.get('commands')

        # Basic input validation
        if not name or not commands_script:
            err_msg = f"Skipping invalid task entry: {todo}. Must have 'name' and 'commands'."
            if verbose:
                _print_locked(print_lock, f"  WARNING: {err_msg}")
            # Store error in results
            final_results[str(name or f"invalid_task_{time.time()}")] = {
                'stdout': '',
                'stderr': err_msg,
                'returncode': -1,
                'pid': None
            }
            continue

        #if verbose:
        #    _print_locked(print_lock, f"  Launching '{name}'...")

        try:
            process = subprocess.Popen(
                ['/bin/bash', '-c', commands_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line-buffered
                encoding='utf-8',
                errors='replace' # Handle potential decoding errors
            )
            pid = process.pid
            process_launch_details.append({'name': name, 'pid': pid})
            #if verbose:
            #    _print_locked(print_lock, f"  '{name}' started with PID: {pid}")

            output_q = queue.Queue()
            threads = []
            process_start_time_task = time.time()

            # Create and start reader threads
            if process.stdout:
                t_out = threading.Thread(
                    target=_stream_reader, args=(process.stdout, output_q, 'stdout'), daemon=True
                )
                t_out.start()
                threads.append(t_out)

            if process.stderr:
                t_err = threading.Thread(
                    target=_stream_reader, args=(process.stderr, output_q, 'stderr'), daemon=True
                )
                t_err.start()
                threads.append(t_err)

            active_processes[process] = {
                'name': name,
                'pid': pid,
                'output_queue': output_q,
                'threads': threads,
                'start_time': process_start_time_task,
                'final_output': {'stdout': [], 'stderr': []}, # Store lines
                'stdout_reader_done': False,
                'stderr_reader_done': False
            }
            # Initialize final results entry
            final_results[name] = {
                'stdout': '', 'stderr': '', 'returncode': None, 'pid': pid
            }

        except Exception as e:
            err_msg = f"ERROR starting '{name}': {e}"
            if verbose:
                _print_locked(print_lock, f"  {err_msg}")
            final_results[name] = {
                'stdout': '', 'stderr': err_msg, 'returncode': -1, 'pid': None
            }

    # --- Print Startup Summary (if verbose) ---
    if verbose and process_launch_details:
        startup_summary = [f"*** Started '{detail['name']}' with PID: {detail['pid']}" for detail in process_launch_details]
        _print_locked(print_lock, f"\n{SEPARATOR}\n" + "\n".join(startup_summary) + f"\n{SEPARATOR}\n\n")

    #if verbose and active_processes:
    #    _print_locked(print_lock, "Monitoring processes...")

    iteration_count = 0
    # --- Main Monitoring Loop ---
    while active_processes:
        iteration_count += 1
        finished_processes_objs = []
        all_queues_empty_this_cycle = True
        # Stores {name: {'stdout': [lines], 'stderr': [lines]}} collected THIS cycle
        output_collected_this_cycle: Dict[str, Dict[str, List[str]]] = {}

        # --- Drain Queues to Collect Recent Output ---
        for proc, data in list(active_processes.items()): # Iterate copy keys
            name = data['name']
            q = data['output_queue']
            output_collected_this_cycle.setdefault(name, {'stdout': [], 'stderr': []})

            try:
                while not q.empty():
                    all_queues_empty_this_cycle = False # Found output
                    stream_name, line = q.get_nowait()

                    if line is None: # Sentinel from reader thread
                        if stream_name == 'stdout': data['stdout_reader_done'] = True
                        elif stream_name == 'stderr': data['stderr_reader_done'] = True
                        continue # Don't process the sentinel itself

                    # Append to final list *and* list for this cycle's status update
                    data['final_output'][stream_name].append(line)
                    output_collected_this_cycle[name][stream_name].append(line)

            except queue.Empty:
                pass # No more output in this queue right now
            except Exception as e:
                # Should be rare, but log if queue access fails mid-run
                stderr_msg = f"\n{SEPARATOR}\n*** WARNING: Exception reading queue for {name}: {e}\n{SEPARATOR}\n\n"
                if verbose: _print_locked(print_lock, stderr_msg, file=sys.stderr)
                # Also add to final stderr for the task
                final_results[name]['stderr'] += stderr_msg


        # --- Periodically Print Status Update (if verbose and enabled) ---
        if verbose and update_interval and (iteration_count % update_interval == 0):
            # Get names of processes still thought to be running
            waiting_on = [(p, d) for p, d in active_processes.items() if p.poll() is None]

            if waiting_on: # Only print status if someone is actually waiting
                waiting_on_names = [d['name'] for p, d in waiting_on]
                try:
                    # Find the start time of the oldest *currently running* process
                    first_start_time = min(d['start_time'] for p, d in waiting_on)
                    current_runtime = time.time() - first_start_time
                except ValueError: # Should not happen if waiting_on is populated
                    current_runtime = time.time() - script_start_time # Fallback
                
                aggregated_stdout_raw_lines = []
                aggregated_stderr_raw_lines = []
                for name in waiting_on_names:
                    cycle_output = output_collected_this_cycle.get(name, {})
                    aggregated_stdout_raw_lines.extend(cycle_output.get('stdout', []))
                    aggregated_stderr_raw_lines.extend(cycle_output.get('stderr', []))

                # Process lines for status update (handles \r, strips ANSI)
                status_stdout_str = _process_status_lines(aggregated_stdout_raw_lines)
                status_stderr_str = _process_status_lines(aggregated_stderr_raw_lines)

                finish_header = f"{SEPARATOR}\n*** Waiting for: {', '.join(waiting_on_names)}\n*** Approx Runtime: {current_runtime:.1f} sec\n{SEPARATOR}\n"
                output_block = _format_output_block(f"*** Output of {name}:", status_stdout_str)
                error_block = _format_output_block(f"*** Error in {name}:", status_stderr_str)
                _print_locked(print_lock, finish_header + output_block + error_block + "\n\n")
                # --- End Status Update Block ---


        # --- Check for Finished Processes ---
        for process, data in list(active_processes.items()): # Iterate copy keys
            return_code = process.poll()
            if return_code is not None: # Process has finished
                name = data['name']
                threads = data['threads']

                # Short wait for reader threads (best effort to catch trailing output)
                for t in threads:
                    t.join(timeout=0.2) # Very short timeout

                # Final drain on queue (just in case thread finished slowly or join timed out)
                q = data['output_queue']
                try:
                    while not q.empty():
                        stream_name, line = q.get_nowait()
                        if line is not None: # Check against sentinel
                            data['final_output'][stream_name].append(line)
                        # Update reader done status if sentinel is found here
                        elif stream_name == 'stdout': data['stdout_reader_done'] = True
                        elif stream_name == 'stderr': data['stderr_reader_done'] = True
                except queue.Empty:
                    pass
                except Exception as e: # Ignore errors on final drain
                    stderr_msg = f"\n*** Warning: Exception on final queue drain for {name}: {e}\n"
                    if verbose: _print_locked(print_lock, stderr_msg, file=sys.stderr)
                    final_results[name]['stderr'] += stderr_msg


                # Assemble final output strings and store results
                final_stdout_raw = "".join(data['final_output']['stdout'])
                final_stderr_raw = "".join(data['final_output']['stderr'])
                # Strip ANSI codes from the full raw output before storing/printing
                final_stdout_stripped = _strip_ansi(final_stdout_raw)
                final_stderr_stripped = _strip_ansi(final_stderr_raw)

                final_results[name].update({
                    'stdout': final_stdout_stripped, # Store stripped
                    'stderr': final_stderr_stripped, # Store stripped
                    'returncode': return_code
                })

                # --- Print Final Summary Block for this process (if verbose) ---
                if verbose:
                    # Print final results using stripped content
                    finish_header = f"{SEPARATOR}\n*** Finished: {name} (RC={return_code})\n{SEPARATOR}\n"
                    # Pass stripped content to the formatter
                    output_block_fmt = _format_output_block(f"*** Output of {name}:", final_stdout_stripped)
                    error_block_fmt = _format_output_block(f"*** Error in {name}:", final_stderr_stripped)
                    _print_locked(print_lock, finish_header + output_block_fmt + error_block_fmt + "\n\n")
                # --- End Final Summary Block ---

                # Mark for removal from active dictionary
                finished_processes_objs.append(process)

        # Remove finished processes from the active dictionary
        if finished_processes_objs:
            for process in finished_processes_objs:
                if process in active_processes:
                    del active_processes[process]

        # Sleep briefly if work remains OR if output was recently processed
        # to avoid busy-waiting while allowing timely checks.
        if active_processes or not all_queues_empty_this_cycle:
            time.sleep(0.5) # Main loop interval


    # --- End of Main Loop ---
    if verbose:
        _print_locked(print_lock, f"{SEPARATOR}\n*** RapidInstall finished.\n{SEPARATOR}\n\n")

    # --- Return final results ---
    # Ensure all originally intended tasks have an entry, even if they failed to start
    for todo in todos:
        name = todo.get('name')
        if name and name not in final_results:
            # This case should be covered by initial error handling, but as a fallback:
            final_results[name] = {
                'stdout': '', 'stderr': 'Task did not start or process was lost',
                'returncode': -1, 'pid': None
            }
            if verbose: _print_locked(print_lock, f"*** WARNING: Task '{name}' missing from final results, assumed failed.", file=sys.stderr)

    return final_results