"""Tracing and observability for FactStack."""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

from factstack.utils.time import get_timestamp, timer


@dataclass
class TraceEntry:
    """A single trace entry representing one pipeline stage."""
    ts: str
    run_id: str
    stage: str
    input_summary: str
    output_summary: str
    latency_ms: float
    ok: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}


class Tracer:
    """Tracer for collecting pipeline execution traces."""
    
    def __init__(self, run_id: Optional[str] = None):
        """Initialize tracer.
        
        Args:
            run_id: Optional run identifier. Generated if not provided.
        """
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.entries: List[TraceEntry] = []
    
    def trace(
        self,
        stage: str,
        input_summary: str,
        output_summary: str,
        latency_ms: float,
        ok: bool = True,
        error: Optional[str] = None,
        **metadata
    ) -> TraceEntry:
        """Add a trace entry.
        
        Args:
            stage: Name of the pipeline stage (e.g., "embed", "vector_search")
            input_summary: Summary of the input to this stage
            output_summary: Summary of the output from this stage
            latency_ms: Execution time in milliseconds
            ok: Whether the stage completed successfully
            error: Error message if ok=False
            **metadata: Additional metadata to include
        
        Returns:
            The created TraceEntry
        """
        entry = TraceEntry(
            ts=get_timestamp(),
            run_id=self.run_id,
            stage=stage,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            ok=ok,
            error=error,
            metadata=metadata if metadata else {}
        )
        self.entries.append(entry)
        return entry
    
    def save(self, path: Path) -> None:
        """Save trace entries to a JSONL file.
        
        Args:
            path: Path to the output file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the trace.
        
        Returns:
            Dictionary with trace summary statistics
        """
        total_latency = sum(e.latency_ms for e in self.entries)
        stages = [e.stage for e in self.entries]
        errors = [e for e in self.entries if not e.ok]
        
        return {
            "run_id": self.run_id,
            "total_entries": len(self.entries),
            "total_latency_ms": total_latency,
            "stages": stages,
            "errors": len(errors),
            "success": len(errors) == 0
        }


class TracedOperation:
    """Context manager for traced operations."""
    
    def __init__(self, tracer: Tracer, stage: str, input_summary: str):
        """Initialize traced operation.
        
        Args:
            tracer: The tracer to use
            stage: Stage name
            input_summary: Summary of input
        """
        self.tracer = tracer
        self.stage = stage
        self.input_summary = input_summary
        self.output_summary = ""
        self.ok = True
        self.error: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self._timer_result = None
    
    def __enter__(self):
        """Enter the context."""
        self._timer_ctx = timer()
        self._timer_result = self._timer_ctx.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and record the trace."""
        self._timer_ctx.__exit__(exc_type, exc_val, exc_tb)
        
        if exc_type is not None:
            self.ok = False
            self.error = str(exc_val)
        
        self.tracer.trace(
            stage=self.stage,
            input_summary=self.input_summary,
            output_summary=self.output_summary,
            latency_ms=self._timer_result.elapsed_ms,
            ok=self.ok,
            error=self.error,
            **self.metadata
        )
        
        # Don't suppress exceptions
        return False
    
    def set_output(self, summary: str) -> None:
        """Set the output summary."""
        self.output_summary = summary
    
    def set_metadata(self, **kwargs) -> None:
        """Set additional metadata."""
        self.metadata.update(kwargs)
    
    def set_error(self, error: str) -> None:
        """Mark operation as failed with an error."""
        self.ok = False
        self.error = error
