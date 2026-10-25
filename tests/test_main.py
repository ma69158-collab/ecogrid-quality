from ecogrid.main import run_demo


def test_demo_runs_end_to_end(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "Accepted 8 readings, rejected 3" in out
    assert "Platform revenue: $0.04" in out
    assert "H2 still offers 4.2 kWh" in out
