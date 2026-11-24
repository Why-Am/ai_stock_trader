"""Safe, deterministic persistence for experiments.

The storage boundary is deliberately file-oriented: domain models remain usable
without a filesystem, while this module owns naming, parsing, and atomic writes.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any, cast

from .errors import DomainValidationError, StorageError
from .models import Experiment, PortfolioConfig, PortfolioState, Trade

STATE_HEADERS = ("date", "cash", "total_value", "holdings")
TRADE_HEADERS = ("date", "action", "ticker", "quantity", "explanation")
_PORTFOLIO_SUFFIXES = ("_state.csv", "_trades.csv", "_strategy.md")


def _json_text(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _atomic_text(path: Path, content: str, *, overwrite: bool = True) -> None:
    """Replace a file in the same directory so readers never see partial data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and path.exists():
        raise StorageError(f"file already exists: {path.name}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if not overwrite and path.exists():
            raise StorageError(f"file already exists: {path.name}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _csv_header(path: Path, headers: tuple[str, ...]) -> None:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    _atomic_text(path, output.getvalue(), overwrite=False)


class ExperimentStorage:
    """Discover, load, create, and append records for experiment directories."""

    def __init__(self, root: Path | str = "experiments") -> None:
        self.root = Path(root)
        self.active = self.root / "active"
        self.finished = self.root / "finished"

    def create(self, experiment: Experiment) -> Path:
        """Create a new active experiment, refusing every existing collision."""
        directory = self.active / experiment.name
        if directory.exists():
            raise StorageError(f"experiment already exists: {experiment.name}")
        self.active.mkdir(parents=True, exist_ok=True)
        directory.mkdir()
        try:
            _atomic_text(
                directory / f"{experiment.name}.json",
                json.dumps(experiment.to_dict(), indent=2, sort_keys=True) + "\n",
                overwrite=False,
            )
            for portfolio in experiment.portfolios:
                _csv_header(directory / f"{portfolio.name}_state.csv", STATE_HEADERS)
                if portfolio.strategy is not None:
                    _atomic_text(
                        directory / f"{portfolio.name}_strategy.md",
                        portfolio.strategy,
                        overwrite=False,
                    )
                    _csv_header(directory / f"{portfolio.name}_trades.csv", TRADE_HEADERS)
        except Exception as exc:
            # Creation is all-or-nothing from the caller's perspective. Cleanup
            # is limited to this newly-created, uniquely named directory.
            for child in directory.iterdir():
                child.unlink()
            directory.rmdir()
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"could not create experiment {experiment.name!r}: {exc}") from exc
        return directory

    def discover(self) -> tuple[Experiment, ...]:
        experiments: list[Experiment] = []
        for parent in (self.active, self.finished):
            if not parent.exists():
                continue
            for directory in sorted(
                (item for item in parent.iterdir() if item.is_dir()), key=lambda p: p.name
            ):
                experiments.append(self.load(directory))
        return tuple(experiments)

    def load(self, directory: Path | str) -> Experiment:
        directory = Path(directory)
        if directory.parent not in (self.active, self.finished) or not directory.is_dir():
            raise StorageError(f"experiment must be inside active or finished storage: {directory}")
        metadata_path = directory / f"{directory.name}.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            experiment = self._parse_metadata(metadata, directory)
            self._validate_contents(directory, experiment)
            return experiment
        except StorageError:
            raise
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise StorageError(f"invalid experiment metadata in {directory.name!r}: {exc}") from exc

    @staticmethod
    def _parse_metadata(metadata: Any, directory: Path) -> Experiment:
        if not isinstance(metadata, dict):
            raise StorageError("experiment metadata must be an object")
        metadata = cast(dict[str, object], metadata)
        required = {"name", "start_date", "end_date", "portfolios"}
        if set(metadata) != required or metadata["name"] != directory.name:
            raise StorageError("experiment metadata has invalid fields or name")
        if not isinstance(metadata["portfolios"], list):
            raise StorageError("experiment portfolios must be a list")
        portfolios: list[PortfolioConfig] = []
        for raw_item in cast(list[object], metadata["portfolios"]):
            item = raw_item
            if not isinstance(item, dict):
                raise StorageError("portfolio metadata must be an object")
            item = cast(dict[str, object], item)
            try:
                portfolio_type = item["type"]
                kwargs: dict[str, Any] = {
                    "name": item["name"],
                    "portfolio_type": portfolio_type,
                    "starting_cash": item["starting_cash"],
                }
                if portfolio_type == "control":
                    if set(item) != {"name", "type", "starting_cash", "control_ticker"}:
                        raise StorageError("control portfolio metadata has invalid fields")
                    kwargs["control_ticker"] = item["control_ticker"]
                elif portfolio_type == "ai-managed":
                    if set(item) != {"name", "type", "starting_cash", "strategy"}:
                        raise StorageError("AI portfolio metadata has invalid fields")
                    # The Markdown file is the authoritative, immutable strategy.
                    kwargs["strategy"] = (directory / f"{item['name']}_strategy.md").read_text(
                        encoding="utf-8"
                    )
                else:
                    raise StorageError("portfolio metadata has invalid type")
                portfolios.append(PortfolioConfig(**kwargs))
            except (KeyError, OSError, DomainValidationError) as exc:
                raise StorageError(f"invalid portfolio metadata: {exc}") from exc
        try:
            return Experiment(
                name=metadata["name"],
                start_date=date.fromisoformat(metadata["start_date"]),
                end_date=date.fromisoformat(metadata["end_date"]),
                portfolios=tuple(portfolios),
            )
        except (TypeError, ValueError, DomainValidationError) as exc:
            raise StorageError(f"invalid experiment metadata: {exc}") from exc

    @staticmethod
    def _validate_contents(directory: Path, experiment: Experiment) -> None:
        expected = {f"{experiment.name}.json"}
        for portfolio in experiment.portfolios:
            expected.add(f"{portfolio.name}_state.csv")
            if portfolio.strategy is not None:
                expected.update({f"{portfolio.name}_strategy.md", f"{portfolio.name}_trades.csv"})
        actual = {item.name for item in directory.iterdir() if item.is_file()}
        missing = expected - actual
        unexpected = actual - expected
        if missing or unexpected:
            details: list[str] = []
            if missing:
                details.append(f"missing {sorted(missing)}")
            if unexpected:
                details.append(f"unexpected {sorted(unexpected)}")
            raise StorageError(f"invalid contents for {directory.name!r}: {'; '.join(details)}")
        for portfolio in experiment.portfolios:
            for suffix, headers in (("_state.csv", STATE_HEADERS), ("_trades.csv", TRADE_HEADERS)):
                path = directory / f"{portfolio.name}{suffix}"
                if path.exists():
                    with path.open(newline="", encoding="utf-8") as handle:
                        if tuple(next(csv.reader(handle), ())) != headers:
                            raise StorageError(f"invalid CSV header in {path.name}")

    def append_state(
        self, directory: Path | str, portfolio_name: str, day: date, state: PortfolioState
    ) -> None:
        path = self._portfolio_file(directory, portfolio_name, "_state.csv")
        row = {
            "date": day.isoformat(),
            "cash": f"{state.cash:.2f}",
            "total_value": f"{state.total_value:.2f}" if state.total_value is not None else "",
            "holdings": _json_text(
                {
                    str(ticker): f"{quantity:.6f}"
                    for ticker, quantity in sorted(state.holdings.items())
                }
            ),
        }
        self._append_csv(path, STATE_HEADERS, [row])

    def append_trades(
        self,
        directory: Path | str,
        portfolio_name: str,
        day: date,
        trades: Iterable[Trade],
        explanation: str,
    ) -> None:
        path = self._portfolio_file(directory, portfolio_name, "_trades.csv")
        rows = [
            {"date": day.isoformat(), **trade.to_dict(), "explanation": explanation.strip()}
            for trade in trades
        ]
        self._append_csv(path, TRADE_HEADERS, rows)

    def _portfolio_file(self, directory: Path | str, portfolio_name: str, suffix: str) -> Path:
        directory = Path(directory)
        if (
            directory.parent not in (self.active, self.finished)
            or directory.name != directory.name.strip()
        ):
            raise StorageError("invalid experiment directory")
        path = directory / f"{portfolio_name}{suffix}"
        if path.parent != directory:
            raise StorageError("invalid portfolio name")
        if not path.is_file():
            raise StorageError(f"portfolio file does not exist: {path.name}")
        return path

    @staticmethod
    def _append_csv(path: Path, headers: tuple[str, ...], rows: Iterable[dict[str, str]]) -> None:
        existing = path.read_text(encoding="utf-8")
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
        if not existing:
            writer.writeheader()
        writer.writerows(rows)
        _atomic_text(path, existing + output.getvalue())


def discover_experiments(root: Path | str = "experiments") -> tuple[Experiment, ...]:
    return ExperimentStorage(root).discover()


def load_experiment(directory: Path | str, root: Path | str = "experiments") -> Experiment:
    return ExperimentStorage(root).load(directory)
