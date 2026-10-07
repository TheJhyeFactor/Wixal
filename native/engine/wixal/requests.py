"""Connection-owned IPC requests with deadlines and acknowledged cancellation."""
import asyncio


LIMITS = {"chat": 600, "task-start": 600, "session-handoff": 110,
          "assessment-run": 600, "tool": 600, "model-import": 1800, "model-pull": 1800,
          "mcp-connect": 300, "memory-recall": 90, "memory-index": 90, "memory-review":120, "legacy-import": 180, "models": 120, "model-status": 120}


class Requests:
    def __init__(self, service, emit):
        self.service, self.emit = service, emit
        self.running = {}

    def start(self, owner, message):
        if not isinstance(message,dict) or not isinstance(message.get("method"),str) or not isinstance(message.get("params",{}),dict):
            raise ValueError("Invalid request envelope")
        identifier = message.get("id")
        if not isinstance(identifier, str) or not identifier or len(identifier)>200:
            raise ValueError("Request needs a bounded string id")
        key = (owner, identifier)
        if key in self.running:
            raise ValueError("Request id is already running")
        task = asyncio.create_task(self.handle(owner, message))
        self.running[key] = task
        task.add_done_callback(lambda finished: self.running.pop(key, None))
        return task

    async def handle(self, owner, message):
        identifier, method = message["id"], message["method"]
        params = message.get("params") or {}
        try:
            if method == "cancel-request":
                target = self.running.get((owner, params.get("id")))
                if target is asyncio.current_task(): raise ValueError("Cannot cancel the cancellation request")
                if target and not target.done():
                    target.cancel()
                    # The target's finally blocks finish before acknowledgement.
                    await asyncio.gather(target, return_exceptions=True)
                result = dict(cancelled=True, id=params.get("id"))
            else:
                async with asyncio.timeout(LIMITS.get(method, 60)):
                    result = await self.service.dispatch(method, params)
            self.emit("response", dict(id=identifier, result=result))
        except asyncio.CancelledError:
            self.emit("response", dict(id=identifier, error="Request cancelled. Check interrupted actions before retrying.", cancelled=True))
        except TimeoutError:
            self.emit("response", dict(id=identifier, error="Request deadline reached. Execution was cancelled; check interrupted actions before retrying.", timedOut=True))
        except Exception as error:
            self.emit("response", dict(id=identifier, error=str(error)))

    async def close(self, owner=None):
        tasks = [task for (client, _), task in list(self.running.items()) if owner is None or client == owner]
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
