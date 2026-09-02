"""The gate that says the recorded book and the live compiler agree.

Nothing here touches the network, including the tests with Compiler Explorer in their names.
Every response they read is committed under tools/cecache/store, through a cache that raises
on a miss, so a test that starts fetching is a test that has stopped checking anything.
"""

from __future__ import annotations

import pathlib
import re
import shlex

import pytest

from gxray import corpus_store
from gxray.__main__ import build_parser
from gxray.driver import CE_FILTERS, CE_RAW, CEBackend
from tools.cecache import OfflineCache, OfflineError
from tools.tier0 import (
    COMPARATORS,
    ROOT,
    Experiment,
    Tier0Error,
    coverage,
    keys,
    load,
    offline,
    online,
    orphans,
    shape,
)

REGISTRY = load()


def test_the_registry_loads_and_says_something():
    assert len(REGISTRY) > 20
    assert {x.kind for x in REGISTRY} == {"recorded", "paired", "offline"}


@pytest.mark.parametrize("x", REGISTRY, ids=lambda x: x.id)
def test_every_experiment_is_offline_clean(x):
    assert offline(x) == []


@pytest.mark.parametrize("x", REGISTRY, ids=lambda x: x.id)
def test_every_experiment_agrees_with_the_cached_live_compiler(x):
    assert online(x, OfflineCache()) == []


def test_nothing_in_the_corpus_or_the_lessons_is_unregistered():
    assert coverage(REGISTRY) == []


def test_the_online_half_never_reaches_the_network():
    """The cache is the whole story in CI, and a miss has to be loud.

    If this ever passes by fetching, the tier 0 parity job stops being a check on the cache
    and becomes a check on whether godbolt.org happens to be up.
    """
    empty = OfflineCache(root="/nonexistent")
    live = next(x for x in REGISTRY if x.kind != "offline")
    problems = online(live, empty)
    assert problems
    assert "not allowed to hit the live API" in problems[0]


def test_a_refusing_cache_refuses_whatever_send_it_is_handed(tmp_path):
    cache = OfflineCache(root=tmp_path)
    with pytest.raises(OfflineError):
        cache.fetch("deadbeef", lambda: {"code": 0, "asm": []})


def test_a_refusing_cache_still_answers_hits(tmp_path):
    cache = OfflineCache(root=tmp_path)
    cache.put("deadbeef", {"code": 0})
    assert cache.fetch("deadbeef", lambda: {"code": 1}) == {"code": 0}


def test_shape_counts_what_the_lessons_assert():
    text = corpus_store.load("t05-boss-O2").dump_texts["tree-ssa"]
    found = shape(text)
    assert found
    one = next(iter(found.values()))
    assert set(one) == set(COMPARATORS) - {"functions"}
    assert one["blocks"] > 1
    assert one["phis"] > 0
    assert one["statements"] == len(one["operators"])


def test_shape_ignores_the_things_a_target_is_allowed_to_change():
    """Two targets, same program, same shape. This is the claim the whole tier rests on."""
    ours = corpus_store.load("t07-aarch64").dump_texts["tree-optimized"]
    theirs = corpus_store.load("t07-x86-64").dump_texts["tree-optimized"]
    assert ours != theirs
    assert shape(ours) == shape(theirs)


def test_an_offline_experiment_has_to_say_why():
    bad = Experiment(id="x", kind="offline", question="why not?")
    assert any("cannot be checked online" in line for line in bad.check())


def test_a_narrowed_comparison_has_to_say_why():
    bad = Experiment(
        id="x", kind="paired", question="q", compiler="cg162", dumps=["tree-ssa"], agree=["blocks"]
    )
    problems = bad.check()
    assert any("does not compare" in line for line in problems)
    assert any("functions" in line and "phis" in line for line in problems)


def test_a_comparison_narrowed_to_nothing_is_rejected():
    bad = Experiment(
        id="x", kind="paired", question="q", compiler="cg162", dumps=["tree-ssa"], agree=[]
    )
    assert any("agrees on nothing" in line for line in bad.check())


def test_a_typo_in_a_comparator_name_is_rejected():
    bad = Experiment(
        id="x", kind="paired", question="q", compiler="cg162", dumps=["a"], agree=["bloks"]
    )
    assert any("no such comparator: bloks" in line for line in bad.check())


def test_two_experiments_cannot_share_an_id(tmp_path):
    p = tmp_path / "experiments.toml"
    p.write_text(
        '[[experiment]]\nid = "a"\nkind = "offline"\nquestion = "q"\nwhy = "w"\n'
        '[[experiment]]\nid = "a"\nkind = "offline"\nquestion = "q"\nwhy = "w"\n'
    )
    with pytest.raises(Tier0Error, match="same id"):
        load(p)


def test_an_experiment_naming_a_corpus_entry_that_is_not_there_is_rejected(tmp_path):
    p = tmp_path / "experiments.toml"
    p.write_text(
        '[[experiment]]\nid = "a"\nkind = "offline"\nquestion = "q"\nwhy = "w"\n'
        'corpus = "no-such-entry"\n'
    )
    with pytest.raises(Tier0Error, match="no corpus entry"):
        load(p)


def test_every_recorded_experiment_names_a_compiler_the_corpus_agrees_with():
    """The registry says which Compiler Explorer compiler made an entry. It has to be right.

    A recorded entry keeps the compiler's own version string, and the ones on the service all
    say Compiler-Explorer-Build or crosstool-NG or plain GCC. A Homebrew string here would
    mean the entry was recorded locally and the registry is calling it something it is not.
    """
    for x in REGISTRY:
        if x.kind != "recorded":
            continue
        assert "Homebrew" not in x.record().compiler, x.id


def test_every_paired_experiment_is_a_local_recording():
    """The other half of the same rule. Pairing a CE entry against CE proves nothing."""
    for x in REGISTRY:
        if x.kind != "paired":
            continue
        assert "Homebrew" in x.record().compiler, x.id


def test_the_store_holds_nothing_nobody_asks_for():
    """A response nothing reads is bandwidth somebody donated and nobody can account for.

    Twenty five experiments justify thirty entries: one request each, minus two that two
    experiments share, plus the `-###` probe behind `version` and `target` for every compiler
    id and filter set, plus the one chain T01 records.
    """
    assert orphans(REGISTRY) == []
    assert len(set().union(*(keys(x) for x in REGISTRY))) == 30


def _ce_recording_recipes():
    """Every `gxray record --backend ce` in the justfile, as parsed argv.

    Read out of the justfile rather than copied into this file, so a recipe added tomorrow is
    covered by the test below without anybody remembering to come back here.
    """
    text = (ROOT / "justfile").read_text(encoding="utf-8")
    joined = re.sub(r"\\\n\s*", " ", text)
    found = []
    for line in joined.splitlines():
        if "gxray record --backend ce" not in line:
            continue
        argv = shlex.split(line.partition("-m gxray ")[2])
        # Same split the real CLI does: anything argparse does not know is a compiler flag.
        args, rest = build_parser().parse_known_args(argv)
        args.flags = rest or ["-O2"]
        found.append(args)
    return found


RECIPES = _ce_recording_recipes()


def test_the_justfile_has_the_ce_recipes_this_test_thinks_it_has():
    assert len(RECIPES) == 9
    assert {a.entry for a in RECIPES} == {
        "t01-driver-ce",
        "t07-x86-64",
        "t07-aarch64",
        "t07-riscv64",
        "t07-power64le",
        "t08-x86-64",
        "t08-aarch64",
        "t09-final",
        "t09-sections",
    }


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda a: a.entry)
def test_every_ce_recording_recipe_replays_with_the_network_off(recipe):
    """Re-recording a Compiler Explorer entry has to work from the committed store.

    Not a nicety. It is what stops the nine entries the book compares against from being
    unreproducible the day the service retires a compiler id, and it is the reason the probe
    behind `version` and `target` is registered alongside the compilation itself.
    """
    filters = CE_RAW if recipe.raw_asm else CE_FILTERS
    backend = CEBackend(recipe.compiler_id, cache=OfflineCache(), filters=dict(filters))
    source = pathlib.Path(recipe.file).read_text(encoding="utf-8")
    backend.compile(source, *recipe.flags, dumps=recipe.dump)
    assert backend.version().startswith("gcc ")
    assert backend.target()
    for spec in recipe.chain or []:
        assert backend.chain(source, *spec.split()).text
