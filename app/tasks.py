import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, Optional


class TaskManager:
    def __init__(self, max_workers: int = 1):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def submit(self, task_type: str, fn, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                "id": task_id,
                "type": task_type,
                "status": "queued",
                "message": "Queued",
                "result": None,
                "error": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

        self.executor.submit(self._run_task, task_id, fn, *args, **kwargs)
        return task_id

    def _run_task(self, task_id: str, fn, *args, **kwargs):
        with self.lock:
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["message"] = "Running"
            self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()

        try:
            result = fn(*args, **kwargs)
            with self.lock:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["message"] = "Completed"
                self.tasks[task_id]["result"] = result
                self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        except Exception as e:
            with self.lock:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["message"] = str(e)
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.tasks.get(task_id)

    def shutdown(self):
        self.executor.shutdown(wait=False)
