"""The three backends.

The local tests drive a real compiler and skip without one. The Compiler Explorer tests
never touch the network: the cache is primed with a recorded response and the backend reads
it, which is exactly how CI runs.
"""

from __future__ import annotations

import json

import pytest

from gxray import corpus_store, gimple, local, programs
from gxray.driver import CE_FILTERS, BackendError, CEBackend, CorpusBackend, LocalBackend, Result
from tools.cecache import Cache, OfflineError, refuse, request_key


def test_capabilities_are_honest():
    assert LocalBackend().can("all-dumps")
    assert not CEBackend().can("all-dumps")
    assert not CEBackend().can("passes")


def test_require_explains_what_the_backend_can_do():
    with pytest.raises(BackendError) as exc:
        CEBackend().require("passes")
    assert "cannot do 'passes'" in str(exc.value)
    assert "It can do:" in str(exc.value)


def test_a_missing_dump_says_what_is_there():
    r = Result(source="", args=(), backend="test", dump_texts={"tree-ssa": ""})
    with pytest.raises(KeyError) as exc:
        r.dump_text("tree-vrp1")
    assert "tree-ssa" in str(exc.value)


@pytest.mark.needs_gcc
def test_local_compiles_and_writes_the_dumps_we_asked_for():
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-ssa", "tree-optimized"])
    assert r.ok
    assert set(r.dump_keys) == {"tree-ssa", "tree-optimized"}
    assert r.dump("tree-ssa").only().name == "f"


@pytest.mark.needs_gcc
def test_local_returns_assembly():
    r = local("gcc-16").compile(programs.L1, "-O2")
    assert "f:" in r.asm or "_f:" in r.asm


@pytest.mark.needs_gcc
def test_the_dumps_land_next_to_the_output_not_next_to_the_input():
    """GCC names dumps after the -o argument. Getting this wrong loses every dump."""
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-ssa"])
    assert r.dump_files, "no dump files found, so -o is pointing somewhere unexpected"
    assert all(d.path.name.startswith("input.c.") for d in r.dump_files)


@pytest.mark.needs_gcc
def test_a_broken_program_fails_without_throwing():
    r = local("gcc-16").compile("int f (void) { return nope; }", "-O2")
    assert not r.ok
    assert "nope" in r.stderr


@pytest.mark.needs_gcc
def test_nothing_in_every_tree_dump_of_l1_is_unparsed():
    """The drift signal. When this number moves, a dump format changed."""
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-all"])
    assert len(r.dump_texts) > 100
    assert r.unparsed_count == 0


@pytest.mark.needs_gcc
def test_the_pipeline_comes_out_of_the_compiler():
    counts = local("gcc-16").pipeline(programs.L1, "-O2").counts()
    assert counts["total"] > 300
    assert counts["enabled"] < counts["total"]


def test_ce_refuses_all_dumps_rather_than_mislabelling_them():
    with pytest.raises(BackendError) as exc:
        CEBackend().compile(programs.L1, "-O2", dumps=["tree-all"])
    assert "nothing separating them" in str(exc.value)


def test_ce_cannot_serve_a_graph_dump_and_says_why():
    """Not a limit we chose. `open_graph_file` in gcc/graph.cc calls `fopen`, so there is no
    way to ask for a dot file on stderr, and CE only ever hands back stderr."""
    with pytest.raises(BackendError) as exc:
        CEBackend().compile(programs.L1, "-O2", dumps=["tree-optimized-graph"])
    assert "never to stderr" in str(exc.value)


@pytest.mark.needs_gcc
def test_the_graph_dump_arrives_beside_the_text_dump_not_instead_of_it():
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-optimized-graph"])
    assert set(r.dump_keys) == {"tree-optimized", "tree-optimized-graph"}
    assert ";; Function f" in r.dump_text("tree-optimized")
    assert r.dump_text("tree-optimized-graph").startswith("digraph")


@pytest.mark.needs_gcc
def test_asking_for_a_control_flow_graph_reaches_for_the_dot_file_on_its_own():
    """Nobody wants to remember the suffix. If the graph is there, it is the honest answer,
    so `cfg("tree-optimized")` reads the dot file and not the text beside it."""
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-optimized-graph"])
    graph = r.cfg("tree-optimized")
    assert graph.function == "f"
    assert graph.check() == []
    assert graph.back_edges, "the loop in l1 has to leave a back edge behind"


@pytest.mark.needs_gcc
def test_a_graph_dump_is_not_counted_as_an_unparsed_gimple_dump():
    """It is a dot file. The drift signal counts dumps the GIMPLE parser choked on, and
    counting this one would make the signal go off for no reason."""
    r = local("gcc-16").compile(programs.L1, "-O2", dumps=["tree-ssa-graph"])
    assert r.unparsed_count == 0


def test_ce_reads_a_primed_cache_and_never_sends(tmp_path):
    """This is how CI runs: the cache is committed, and a miss is a hard error."""
    cache = Cache(root=tmp_path)
    backend = CEBackend("cg162", cache=cache)
    args = "-O2 -fdump-tree-ssa=stderr"
    key = request_key("cg162", programs.L1, args, CE_FILTERS)
    cache.put(
        key,
        {"code": 0, "stderr": [{"text": ";; Function f (f)"}, {"text": "int f ()"}], "asm": []},
    )

    r = backend.compile(programs.L1, "-O2", dumps=["tree-ssa"])
    assert r.ok
    assert "Function f" in r.dump_text("tree-ssa")
    assert cache.hits == 1


def test_the_cache_refuses_to_go_online_when_told_to(tmp_path):
    cache = Cache(root=tmp_path)
    with pytest.raises(OfflineError):
        cache.fetch("nothing-here", refuse)


def test_corpus_backend_serves_recorded_dumps(tmp_path):
    rec = corpus_store.Record(
        entry="demo",
        source=programs.L1,
        args=["-O2"],
        compiler="gcc-16 (Homebrew GCC 16.2.0) 16.2.0",
        target="aarch64-apple-darwin24",
        recorded="2026-09-01",
        dump_texts={"tree-ssa": ";; Function f (f)\nint f ()\n"},
    )
    corpus_store.save(rec, root=tmp_path)

    r = CorpusBackend("demo", root=tmp_path).compile(programs.L1, "-O2", dumps=["tree-ssa"])
    assert r.ok
    assert "Function f" in r.dump_text("tree-ssa")


def test_corpus_says_so_when_the_dump_was_never_recorded(tmp_path):
    rec = corpus_store.Record("demo", "", [], "gcc", "target", "2026-09-01", {"tree-ssa": ""})
    corpus_store.save(rec, root=tmp_path)
    with pytest.raises(BackendError) as exc:
        CorpusBackend("demo", root=tmp_path).compile("", dumps=["tree-vrp1"])
    assert "whatever somebody recorded" in str(exc.value)


def test_corpus_round_trips_through_json(tmp_path):
    rec = corpus_store.Record(
        "demo", "int f;", ["-O1"], "gcc", "t", "2026-09-01", {"a": "b"}, "asm"
    )
    path = corpus_store.save(rec, root=tmp_path)
    back = corpus_store.Record.from_json(json.loads(path.read_text()))
    assert back == rec
    assert corpus_store.entries(root=tmp_path) == ["demo"]


def test_the_recorded_pass_lists_round_trip_too(tmp_path):
    """The pass list is recorded per set of flags, because it is different at every
    optimization level and T04 is partly about that difference."""
    rec = corpus_store.Record(
        "demo",
        "int f;",
        ["-O2"],
        "gcc",
        "t",
        "2026-09-01",
        {"a": "b"},
        pass_texts={"-O0": "  tree-cfg : ON\n", "-O2": "  tree-cfg : ON\n  tree-pre : ON\n"},
    )
    path = corpus_store.save(rec, root=tmp_path)
    back = corpus_store.Record.from_json(json.loads(path.read_text()))
    assert back == rec
    assert sorted(back.pass_texts) == ["-O0", "-O2"]


def test_an_older_recording_with_no_pass_lists_still_loads(tmp_path):
    """Every entry recorded before T04 has no `passes` key, and none of them should have to
    be re-recorded to stay readable."""
    (tmp_path / "old.json").write_text(
        json.dumps(
            {
                "entry": "old",
                "source": "",
                "args": [],
                "compiler": "gcc",
                "target": "t",
                "recorded": "2026-09-01",
                "dumps": {},
            }
        )
    )
    assert corpus_store.load("old", root=tmp_path).pass_texts == {}


def test_a_missing_corpus_entry_lists_the_ones_that_exist(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        corpus_store.load("nope", root=tmp_path)
    assert "Recorded entries: none" in str(exc.value)


def test_the_parsed_dump_is_cached():
    r = Result(source="", args=(), backend="t", dump_texts={"d": ";; Function f (f)\nint f ()\n"})
    assert r.dump("d") is r.dump("d")
    assert isinstance(r.dump("d"), gimple.GimpleDump)
