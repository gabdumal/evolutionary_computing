from optimization_experiments.core import TimingResult
from optimization_experiments.execution.runner import _format_duration


def test_timing_result_accepts_cpu_and_wall_time():
    timing = TimingResult(cpu_seconds=1.25, wall_seconds=2.5)
    assert timing.cpu_seconds == 1.25
    assert timing.wall_seconds == 2.5


def test_timing_result_rejects_negative_wall_time():
    try:
        TimingResult(cpu_seconds=0.0, wall_seconds=-1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative wall time should be rejected.")


def test_format_duration():
    assert _format_duration(0) == "0.00s"
    assert _format_duration(0.836) == "0.84s"
    assert _format_duration(61) == "00:01:01"
    assert _format_duration(3661) == "01:01:01"
    assert _format_duration(86_401) == "1d 00:00:01"
