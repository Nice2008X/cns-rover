"""Local FastAPI service for the MaleCNS experiment workbench."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import threading
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .workbench import Workbench, validate_config


def create_app(scenario, factory, root="runs/workbench", controller="baseline", model=None, port=8765):
    bench = Workbench(scenario, factory, root, controller, model)
    @asynccontextmanager
    async def lifespan(app):
        worker = threading.Thread(target=bench.worker, daemon=True)
        worker.start()
        yield
        bench.closed.set()
        bench.batch_cancel.set()
        await asyncio.to_thread(worker.join, 5)
        if hasattr(bench, "batch_thread"):
            await asyncio.to_thread(bench.batch_thread.join, 5)
        with bench.lock:
            bench.current.finish("server_shutdown")

    app = FastAPI(title="MaleCNS Simulator", lifespan=lifespan)
    app.state.workbench = bench

    def origin_allowed(origin, host):
        return not origin or origin in {f"http://{host}", f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://127.0.0.1:5173", "http://localhost:5173"}

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Invalid host"}, status_code=403)
        if request.method != "GET" and not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
            return JSONResponse({"detail": "Invalid origin"}, status_code=403)
        try:
            if int(request.headers.get("content-length", 0)) > 65536:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.get("/api/state")
    def state():
        return bench.state()

    @app.get("/api/runs")
    def runs():
        return bench.store.list()

    @app.get("/api/runs/{run_id}/history")
    def history(run_id: str):
        # Frames are retrieved on demand, not duplicated in the chart stream.
        return bench.store.records(run_id)

    @app.get("/api/runs/{run_id}/frames/{index}")
    def frame(run_id: str, index: int):
        return bench.store.snapshot(run_id, index)

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str):
        path = bench.store.directory(run_id)
        return FileResponse(path/"snapshots.jsonl", media_type="application/x-ndjson", filename=f"{run_id}.jsonl")

    @app.get("/api/presets")
    def presets():
        from .scenario import Scenario
        return [{"label": "Simple arena", "scenario": Scenario().to_dict()}, {"label": "Target behind vehicle", "scenario": Scenario(name="behind", start=[2., 2., 180.]).to_dict()}, {"label": "Occluded target", "scenario": Scenario(name="obstacle", start=[2., 5., 0.], target=[7., 5., .15], obstacles=[[4., 5., .45]]).to_dict()}]

    @app.post("/api/validate")
    def validate(payload: dict):
        return validate_config(payload)

    @app.post("/api/batch")
    def batch(payload: dict):
        return bench.start_batch(payload)

    @app.post("/api/batch/cancel")
    def cancel_batch():
        bench.batch_cancel.set()
        return {"ok": True}

    @app.post("/api/{action}")
    def action(action: str, payload: dict):
        try:
            return bench.action(action, payload)
        except TypeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.websocket("/api/stream")
    async def stream(ws: WebSocket):
        host = ws.headers.get("host", "")
        if host.split(":")[0] not in {"localhost", "127.0.0.1", "testserver"} or not origin_allowed(ws.headers.get("origin"), host):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while True:
                await ws.send_json(await asyncio.to_thread(bench.state))
                await asyncio.sleep(.1)
        except (WebSocketDisconnect, RuntimeError):
            pass

    web = Path(__file__).parent / "web"
    if web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="frontend")
    else:
        @app.get("/")
        def build_required():
            return JSONResponse({"message": "Build the frontend: npm ci --prefix frontend && npm run build --prefix frontend"}, status_code=503)
    return app


def serve(scenario, factory, port=8765, controller="baseline", model=None):
    import uvicorn
    uvicorn.run(create_app(scenario, factory, controller=controller, model=model, port=port), host="127.0.0.1", port=port)
