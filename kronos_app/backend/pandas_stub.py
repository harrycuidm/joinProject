"""A minimal pandas compatibility layer for offline testing.

This stub provides just enough surface area for the unit tests and service
layer to run in environments where the real pandas dependency cannot be
installed.  It should not be used in production workloads - deployers must
install pandas to unlock the full functionality of the data providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

Number = Union[int, float]


def _coerce_datetime(value: Union["Timestamp", datetime, date, str, None]) -> Optional[datetime]:
    """Return a ``datetime`` for the given value, accepting common inputs."""

    if value is None:
        return None
    if isinstance(value, Timestamp):
        return value._dt
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            if len(value) == 8 and value.isdigit():
                return datetime.strptime(value, "%Y%m%d")
            raise
    raise TypeError(f"Cannot interpret {value!r} as a datetime")


class Timestamp:
    """Lightweight timestamp wrapper that mimics the pandas API we rely on."""

    __slots__ = ("_dt",)

    def __init__(self, value: Union["Timestamp", datetime, date, str]) -> None:
        dt = _coerce_datetime(value)
        if dt is None:
            raise TypeError("Timestamp cannot be constructed from None")
        self._dt = dt

    def date(self) -> date:
        return self._dt.date()

    def to_pydatetime(self) -> datetime:
        return self._dt

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Timestamp('{self._dt.isoformat()}')"

    def __hash__(self) -> int:  # pragma: no cover - allow dictionary usage
        return hash(self._dt)

    def _compare(self, other: Any, op) -> bool:
        other_dt = _coerce_datetime(other)
        if other_dt is None:
            raise TypeError(f"Cannot compare Timestamp with {other!r}")
        return op(self._dt, other_dt)

    def __lt__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a < b)

    def __le__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a <= b)

    def __gt__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a > b)

    def __ge__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a >= b)

    def __eq__(self, other: Any) -> bool:
        try:
            return self._dt == _coerce_datetime(other)
        except TypeError:
            return False

    def __add__(self, other: Any) -> "Timestamp":
        if isinstance(other, BDay):
            dt = self._dt
            steps = other.n
            direction = 1 if steps >= 0 else -1
            remaining = abs(steps)
            while remaining:
                dt += timedelta(days=direction)
                if dt.weekday() < 5:
                    remaining -= 1
            return Timestamp(dt)
        if isinstance(other, timedelta):
            return Timestamp(self._dt + other)
        return NotImplemented

    def __sub__(self, other: Any) -> Union["Timestamp", timedelta]:
        if isinstance(other, BDay):
            return self + BDay(-other.n)
        other_dt = _coerce_datetime(other)
        if other_dt is None:
            return NotImplemented
        return self._dt - other_dt


class BDay:
    """Business day offset supporting addition and subtraction."""

    def __init__(self, n: int = 1) -> None:
        self.n = int(n)

    def __mul__(self, value: int) -> "BDay":  # pragma: no cover - pandas compatibility
        return BDay(self.n * int(value))

    __rmul__ = __mul__


class _Offsets:
    BDay = BDay


class _TSeries:
    offsets = _Offsets()


tseries = _TSeries()


def bdate_range(start: Union[str, date, datetime], periods: int) -> List[Timestamp]:
    """Generate a list of business-day ``Timestamp`` objects."""

    start_dt = _coerce_datetime(start)
    if start_dt is None:
        raise TypeError("bdate_range requires a valid start date")
    current = Timestamp(start_dt)
    while current._dt.weekday() >= 5:
        current = Timestamp(current._dt + timedelta(days=1))
    results: List[Timestamp] = []
    while len(results) < periods:
        if current._dt.weekday() < 5:
            results.append(Timestamp(current))
        current = Timestamp(current._dt + timedelta(days=1))
    return results


@dataclass
class Series:
    """Minimal Series implementation that supports the operations we use."""

    _data: List[Any]
    index: List[Any]

    def __init__(self, data: Iterable[Any], index: Optional[Iterable[Any]] = None) -> None:
        values = list(data)
        if index is None:
            index_list = list(range(len(values)))
        else:
            index_list = [Timestamp(item) if isinstance(item, (date, datetime, str)) else item for item in index]
        if len(index_list) != len(values):
            raise ValueError("Series data and index must have the same length")
        self._data = values
        self.index = index_list

    def items(self) -> Iterator[Tuple[Any, Any]]:
        return iter(zip(self.index, self._data))

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __getitem__(self, key: Union[int, slice]) -> Any:
        if isinstance(key, slice):
            return Series(self._data[key], self.index[key])
        return self._data[key]

    def dropna(self) -> "Series":
        new_data: List[Any] = []
        new_index: List[Any] = []
        for idx, value in zip(self.index, self._data):
            if value is None:
                continue
            if isinstance(value, float) and value != value:  # NaN check
                continue
            new_index.append(idx)
            new_data.append(value)
        return Series(new_data, new_index)

    def pct_change(self) -> "Series":
        previous: Optional[Number] = None
        changes: List[Optional[float]] = []
        for value in self._data:
            numeric = float(value)
            if previous is None or previous == 0:
                changes.append(None)
            else:
                changes.append((numeric - previous) / previous)
            previous = numeric
        return Series(changes, self.index)

    def astype(self, target_type: Any) -> "Series":  # pragma: no cover - narrow use case
        if target_type is float:
            return Series([float(value) for value in self._data], self.index)
        raise TypeError("pandas_stub Series only supports conversion to float")

    def to_list(self) -> List[Any]:  # pragma: no cover - debugging helper
        return list(self._data)

    def __eq__(self, other: Any) -> "Series":
        return Series([value == other for value in self._data], self.index)

    def __and__(self, other: "Series") -> "Series":
        return Series([bool(a) and bool(b) for a, b in zip(self._data, other._data)], self.index)

    def between(self, left: Any, right: Any) -> "Series":
        left_dt = _coerce_datetime(left)
        right_dt = _coerce_datetime(right)
        flags: List[bool] = []
        for value in self._data:
            current = _coerce_datetime(value)
            if current is None:
                flags.append(False)
                continue
            left_ok = True if left_dt is None else current >= left_dt
            right_ok = True if right_dt is None else current <= right_dt
            flags.append(left_ok and right_ok)
        return Series(flags, self.index)

    class _StringAccessor:
        def __init__(self, series: "Series") -> None:
            self._series = series

        def upper(self) -> "Series":
            return Series([str(value).upper() if value is not None else None for value in self._series._data], self._series.index)

    @property
    def str(self) -> "Series._StringAccessor":  # pragma: no cover - compatibility hook
        return Series._StringAccessor(self)


class DataFrame:
    """A very small subset of the pandas ``DataFrame`` interface."""

    def __init__(self, data: Optional[Dict[str, Iterable[Any]]] = None, index: Optional[Iterable[Any]] = None) -> None:
        data = data or {}
        columns = {key: list(values) for key, values in data.items()}
        lengths = {len(values) for values in columns.values()}
        if lengths:
            if len(lengths) != 1:
                raise ValueError("All DataFrame columns must have the same length")
            length = lengths.pop()
        else:
            length = 0
        if index is None:
            index_list = list(range(length))
        else:
            index_list = [Timestamp(item) if isinstance(item, (date, datetime, str)) else item for item in index]
            if len(index_list) != length:
                raise ValueError("Index length must match data length")
        self._data = columns
        self.index = index_list

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, key: str) -> Series:
        return Series(self._data[key], self.index)

    def __setitem__(self, key: str, value: Iterable[Any]) -> None:
        values = list(value)
        if len(values) != len(self.index):
            raise ValueError("Assigned values must match DataFrame length")
        self._data[key] = values

    @property
    def empty(self) -> bool:
        return len(self.index) == 0

    def sort_values(self, column: str) -> "DataFrame":
        order = sorted(range(len(self.index)), key=lambda idx: self._data[column][idx])
        new_data = {col: [values[idx] for idx in order] for col, values in self._data.items()}
        new_index = [self.index[idx] for idx in order]
        return DataFrame(new_data, new_index)

    def set_index(self, column: str) -> "DataFrame":
        new_index = [Timestamp(value) if not isinstance(value, Timestamp) else value for value in self._data[column]]
        new_data = {col: values for col, values in self._data.items() if col != column}
        return DataFrame(new_data, new_index)

    def rename(self, columns: Dict[str, str]) -> "DataFrame":
        renamed = {columns.get(col, col): values for col, values in self._data.items()}
        return DataFrame(renamed, self.index)

    def loc(self) -> "_LocIndexer":  # pragma: no cover - compatibility wrapper
        return _LocIndexer(self)

    def iloc(self) -> "_ILocIndexer":  # pragma: no cover - compatibility wrapper
        return _ILocIndexer(self)

    # Provide property-style access like pandas
    loc = property(loc)
    iloc = property(iloc)


class _LocIndexer:
    def __init__(self, frame: DataFrame) -> None:
        self._frame = frame

    def __getitem__(self, key: Union[slice, Series]) -> DataFrame:
        if isinstance(key, slice):
            start_dt = _coerce_datetime(key.start)
            stop_dt = _coerce_datetime(key.stop)
            new_index: List[Any] = []
            positions: List[int] = []
            for idx, label in enumerate(self._frame.index):
                label_dt = _coerce_datetime(label)
                if start_dt is not None and label_dt is not None and label_dt < start_dt:
                    continue
                if stop_dt is not None and label_dt is not None and label_dt > stop_dt:
                    continue
                new_index.append(label)
                positions.append(idx)
            new_data = {col: [values[pos] for pos in positions] for col, values in self._frame._data.items()}
            return DataFrame(new_data, new_index)
        if isinstance(key, Series):
            if len(key) != len(self._frame.index):
                raise ValueError("Boolean indexer must match DataFrame length")
            new_index = []
            positions = []
            for idx, flag in enumerate(key):
                if flag:
                    new_index.append(self._frame.index[idx])
                    positions.append(idx)
            new_data = {col: [values[pos] for pos in positions] for col, values in self._frame._data.items()}
            return DataFrame(new_data, new_index)
        raise TypeError("Unsupported indexer for DataFrame.loc")


class _ILocIndexer:
    def __init__(self, frame: DataFrame) -> None:
        self._frame = frame

    def __getitem__(self, key: slice) -> DataFrame:
        indices = list(range(len(self._frame.index)))[key]
        new_index = [self._frame.index[pos] for pos in indices]
        new_data = {col: [values[pos] for pos in indices] for col, values in self._frame._data.items()}
        return DataFrame(new_data, new_index)


def to_datetime(values: Iterable[Any], fmt: str | None = None) -> List[datetime]:  # pragma: no cover - CSV helper
    result: List[datetime] = []
    for value in values:
        if isinstance(value, str) and fmt:
            result.append(datetime.strptime(value, fmt))
        else:
            dt = _coerce_datetime(value)
            if dt is None:
                raise TypeError("Cannot convert value to datetime")
            result.append(dt)
    return result


def read_csv(path: Union[str, "PathLike[str]"]) -> DataFrame:  # pragma: no cover - CSV helper
    import csv
    from pathlib import Path

    fp = Path(path)
    with fp.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        return DataFrame()
    columns: Dict[str, List[Any]] = {}
    for key in rows[0].keys():
        columns[key] = [row[key] for row in rows]
    return DataFrame(columns)


IS_STUB = True


__all__ = [
    "BDay",
    "DataFrame",
    "IS_STUB",
    "Series",
    "Timestamp",
    "bdate_range",
    "read_csv",
    "tseries",
    "to_datetime",
]
