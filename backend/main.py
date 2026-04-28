"""
main.py — FastAPI application: REST + WebSocket endpoints.
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from net_monitor import get_rate
from tc_runner import (
    ALLOWED_RATES,
    clear_rate,
    get_interfaces,
    get_qdisc,
    set_rate,
)

app = FastAPI(title="Linux Traffic Shaper", version="2.0.0")

# Allow localhost origins only for local `npm run dev` convenience.
# In production Caddy proxies all traffic from the same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IfaceResponse(BaseModel):
    name: str
    iface_type: str


class StatusResponse(BaseModel):
    iface: str
    rate_kbps: Optional[int] = None
    active: bool


class ApplyRequest(BaseModel):
    iface: str
    rate_kbps: int

    @field_validator("rate_kbps")
    @classmethod
    def must_be_allowed(cls, v: int) -> int:
        if v not in ALLOWED_RATES:
            raise ValueError(
                f"rate_kbps must be one of {sorted(ALLOWED_RATES)}"
            )
        return v


class RatesResponse(BaseModel):
    rates: list[int]


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/interfaces", response_model=list[IfaceResponse])
def api_interfaces() -> list[IfaceResponse]:
    ifaces = get_interfaces()
    return [IfaceResponse(name=i.name, iface_type=i.iface_type) for i in ifaces]


@app.get("/api/rates", response_model=RatesResponse)
def api_rates() -> RatesResponse:
    return RatesResponse(rates=sorted(ALLOWED_RATES.keys()))


@app.get("/api/status/{iface}", response_model=StatusResponse)
def api_status(iface: str) -> StatusResponse:
    try:
        rate = get_qdisc(iface)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return StatusResponse(iface=iface, rate_kbps=rate, active=rate is not None)


@app.post("/api/apply", response_model=StatusResponse)
def api_apply(req: ApplyRequest) -> StatusResponse:
    try:
        set_rate(req.iface, req.rate_kbps)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    rate = get_qdisc(req.iface)
    return StatusResponse(iface=req.iface, rate_kbps=rate, active=rate is not None)


@app.delete("/api/clear/{iface}", response_model=StatusResponse)
def api_clear(iface: str) -> StatusResponse:
    try:
        clear_rate(iface)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return StatusResponse(iface=iface, rate_kbps=None, active=False)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/stats")
async def ws_stats(websocket: WebSocket, iface: str = "") -> None:
    """Stream NetSamples as JSON every 500 ms for the requested interface."""
    if not iface:
        await websocket.close(code=1008, reason="iface query param required")
        return
    await websocket.accept()
    try:
        async for sample in get_rate(iface):
            await websocket.send_json(
                {
                    "rx_kbps": round(sample.rx_kbps, 1),
                    "tx_kbps": round(sample.tx_kbps, 1),
                    "ts": sample.ts,
                }
            )
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        await websocket.close(code=1011, reason=str(e))
