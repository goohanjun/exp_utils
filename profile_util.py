import time
import os
import psutil
import inspect
import linecache
import tracemalloc
from datetime import datetime
from queue import Queue, Empty
from threading import Thread


# Example 1.
def display_top(snapshot, key_type="lineno", limit=5):
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        print(
            "#%s: %s:%s: %.1f KiB" % (index, filename, frame.lineno, stat.size / 1024)
        )
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print("    %s" % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))


# Example 2.
def elapsed_since(start):
    elapsed = time.time() - start
    if elapsed < 1:
        return str(round(elapsed * 1000, 2)) + "ms"
    if elapsed < 60:
        return str(round(elapsed, 2)) + "s"
    if elapsed < 3600:
        return str(round(elapsed / 60, 2)) + "min"
    else:
        return str(round(elapsed / 3600, 2)) + "hrs"


def get_process_memory():
    process = psutil.Process(os.getpid())
    mi = process.memory_info()
    return mi.rss, mi.vms


def format_bytes(bytes):
    if abs(bytes) < 1000:
        return str(bytes) + "B"
    elif abs(bytes) < 1e6:
        return str(round(bytes / 1e3, 2)) + "kB"
    elif abs(bytes) < 1e9:
        return str(round(bytes / 1e6, 2)) + "MB"
    else:
        return str(round(bytes / 1e9, 2)) + "GB"


def profile(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        rss_before, vms_before = get_process_memory()
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_time = elapsed_since(start)
        rss_after, vms_after = get_process_memory()
        print(
            "Profiling: {:>20}  RSS: {:>8} | VMS: {:>8} | time: {:>8}".format(
                "<" + func.__name__ + ">",
                format_bytes(rss_after - rss_before),
                format_bytes(vms_after - vms_before),
                elapsed_time,
            )
        )
        return result

    if inspect.isfunction(func):
        return wrapper
    elif inspect.ismethod(func):
        return wrapper(*args, **kwargs)


# Example 3
def memory_monitor(command_queue: Queue, poll_interval=1):
    tracemalloc.start()
    old_max = 0
    snapshot = None
    while True:
        try:
            command_queue.get(timeout=poll_interval)
            if snapshot is not None:
                print("Monitoring is over @", datetime.now())
                print(" < Overall snapshot info >")
                display_top(snapshot)
            return
        except Empty:
            curr_rss, _ = get_process_memory()
            # curr_rss = getrusage(RUSAGE_SELF).ru_maxrss
            if curr_rss > old_max:
                old_max = curr_rss
                snapshot = tracemalloc.take_snapshot()
            print(
                "MEM Usage::",
                datetime.now(),
                "max RSS",
                format_bytes(old_max),
                "current RSS",
                format_bytes(curr_rss),
            )


class BackgroundMemoryMonitor:
    def __init__(self, poll_interval=3):

        self.q = Queue()
        self.poll_interval = poll_interval
        self.monitor_thread = Thread(
            target=memory_monitor, args=(self.q, poll_interval)
        )

    def start(self):
        self.monitor_thread.start()

    def stop(self):
        self.q.put("stop")
        self.monitor_thread.join()


def workload(a, b):
    cnt = 0
    tmp_list = []
    while cnt < a ** b:
        tmp_list.append(a * b + cnt)
        cnt += 1
    return tmp_list


if __name__ == "__main__":
    print("Profile examples")

    a, b = 70.41, 3.21

    m_monitor = BackgroundMemoryMonitor(poll_interval=3.0)
    m_monitor.start()

    tracemalloc.start()
    # do something
    print("\nExample # 1")
    cnt_out = workload(a, b)
    snapshot = tracemalloc.take_snapshot()
    display_top(snapshot)

    print("\nExample # 2")
    cnt_out = profile(workload)(a, b)

    print("\nExample # 3")
    m_monitor.stop()
