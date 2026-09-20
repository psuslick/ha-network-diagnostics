"""Data models for Network Diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .classifier import DiagnosisResult


@dataclass(slots=True)
class IncidentTransition:
    at: str
    diagnosis: str
    confidence: str
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IncidentRecord:
    id: str
    started_at: str
    initial_diagnosis: str
    current_diagnosis: str
    confidence: str
    summary: str
    transitions: list[IncidentTransition]
    start_snapshot: dict[str, Any]
    latest_snapshot: dict[str, Any]
    fingerprint: str = ""
    ended_at: str | None = None
    duration_seconds: int | None = None
    recovered_snapshot: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["transitions"] = [asdict(item) for item in self.transitions]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IncidentRecord":
        transitions = [IncidentTransition(**item) for item in data.get("transitions", [])]
        return cls(
            id=data["id"],
            started_at=data["started_at"],
            initial_diagnosis=data["initial_diagnosis"],
            current_diagnosis=data.get("current_diagnosis", data["initial_diagnosis"]),
            confidence=data.get("confidence", "unknown"),
            summary=data.get("summary", ""),
            transitions=transitions,
            start_snapshot=data.get("start_snapshot", {}),
            latest_snapshot=data.get("latest_snapshot", {}),
            fingerprint=data.get("fingerprint", ""),
            ended_at=data.get("ended_at"),
            duration_seconds=data.get("duration_seconds"),
            recovered_snapshot=data.get("recovered_snapshot"),
        )


@dataclass(slots=True)
class RuntimeSnapshot:
    at: str
    diagnosis: DiagnosisResult
    observations: list[dict[str, Any]]
    discovery: dict[str, Any]
    provider_freshness: dict[str, Any]
    manual: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "manual": self.manual,
            "diagnosis": {
                "diagnosis": self.diagnosis.diagnosis,
                "summary": self.diagnosis.summary,
                "confidence": self.diagnosis.confidence,
                "evidence": list(self.diagnosis.evidence),
                "contradictions": list(self.diagnosis.contradictions),
                "downstream": list(self.diagnosis.downstream),
                "unaffected": list(self.diagnosis.unaffected),
                "failed_controls": list(self.diagnosis.failed_controls),
                "affected_components": list(self.diagnosis.affected_components),
                "monitoring_gaps": list(self.diagnosis.monitoring_gaps),
                "coverage_gaps": list(self.diagnosis.coverage_gaps),
                "unassigned_monitors": list(self.diagnosis.unassigned_monitors),
                "root_causes": [
                    {
                        "name": cause.name,
                        "domain": cause.domain,
                        "confidence": cause.confidence,
                        "supporting": list(cause.supporting),
                        "contradicting": list(cause.contradicting),
                        "downstream": list(cause.downstream),
                        "affected": list(cause.affected),
                        "causal_path": list(cause.causal_path),
                    }
                    for cause in self.diagnosis.root_causes
                ],
            },
            "observations": list(self.observations),
            "discovery": dict(self.discovery),
            "provider_freshness": dict(self.provider_freshness),
        }
