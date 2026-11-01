"""Detached session financial receipts. Structural values are not authority."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json

from app.research_contracts import SessionArtifactRef, encode

MAX_RECEIPT_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class SessionObservationRef:
    artifact: SessionArtifactRef
    fact_locator: str
    context_locator: str
    metric: str
    value: Decimal
    unit: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class SessionInput:
    role: str
    metric: str
    value: Decimal
    unit: str
    observations: tuple[SessionObservationRef, ...]


@dataclass(frozen=True, slots=True)
class SessionFinancialResult:
    artifact: SessionArtifactRef
    metric: str
    fiscal_year: int
    status: str
    value: Decimal | None
    reason: str | None
    start: date | None
    end: date | None
    formula: str | None
    selection_version: str
    mapping_version: str
    parser_version: str
    observations: tuple[SessionObservationRef, ...]
    alternatives: tuple[SessionObservationRef, ...]
    inputs: tuple[SessionInput, ...]

    def encode(self):
        if (type(self.artifact) is not SessionArtifactRef or type(self.observations) is not tuple
                or type(self.alternatives) is not tuple or type(self.inputs) is not tuple):
            raise ValueError("invalid_receipt")
        refs = self.observations + self.alternatives
        if any(type(item) is not SessionInput or type(item.observations) is not tuple for item in self.inputs):
            raise ValueError("invalid_receipt")
        refs += tuple(ref for item in self.inputs for ref in item.observations)
        if any(type(item) is not SessionObservationRef or item.artifact != self.artifact for item in refs):
            raise ValueError("invalid_receipt")
        def observation(item):
            return {"fact_locator": item.fact_locator, "context_locator": item.context_locator,
                    "metric": item.metric, "value": str(item.value), "unit": item.unit,
                    "start": item.start.isoformat(), "end": item.end.isoformat()}
        payload = {
            "artifact": json.loads(encode(self.artifact)), "metric": self.metric, "fiscal_year": self.fiscal_year,
            "status": self.status, "value": str(self.value) if self.value is not None else None,
            "reason": self.reason, "period": {"start": self.start.isoformat() if self.start else None,
                                              "end": self.end.isoformat() if self.end else None},
            "formula": self.formula, "selection_version": self.selection_version,
            "mapping_version": self.mapping_version, "parser_version": self.parser_version,
            "observations": [observation(item) for item in self.observations],
            "alternatives": [observation(item) for item in self.alternatives],
            "inputs": [{"role": item.role, "metric": item.metric, "value": str(item.value),
                        "unit": item.unit, "observations": [observation(ref) for ref in item.observations]}
                       for item in self.inputs],
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_RECEIPT_BYTES:
            raise ValueError("receipt_too_large")
        return encoded
