"""The build matrix.

None of this needs Docker, a registry, or the pinned GCC tree. `containers/matrix.toml` is
one TOML file and everything here reads it, which is the reason the matrix is a TOML file
and not a workflow with the flags typed into it.
"""

from __future__ import annotations

import json
import textwrap

import pytest
import yaml

from tools import matrix

FOUND = matrix.load()
WORKFLOW = matrix.REPO_ROOT / ".github" / "workflows" / "build-matrix.yml"


def write(tmp_path, body: str):
    path = tmp_path / "matrix.toml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


ONE = """
    tag = "releases/gcc-16.2.0"
    registry = "ghcr.io/x/y"

    [common]
    languages = "c"
    install = "install-strip"
    smoke = "gcc -O2 /tmp/t.c -o /tmp/t"
    configure = ["--prefix=/opt/gcc"]

    [[config]]
    id = "rel"
    purpose = "p"
    why = "w"
    configure = ["--disable-bootstrap"]
    cflags = "-O2"
    make = "all"
    arches = ["amd64"]
    weekly = true
    on_patches = true
    minutes = 25
    gigabytes = 1.2
"""


def test_the_six_configurations_are_the_six_the_book_talks_about():
    assert [c.id for c in FOUND.configs] == ["rel", "chk", "dbg", "boot", "cross", "plug"]


def test_every_configuration_builds_for_both_architectures():
    """A reader on an arm64 laptop is not a special case, and half of them are."""
    for config in FOUND.configs:
        assert set(config.arches) == set(matrix.ARCHES), config.id


def test_the_shared_flags_come_first_and_are_not_repeated_in_a_configuration():
    for config in FOUND.configs:
        if not config.from_source:
            continue
        assert config.flags[: len(config.common)] == list(config.common), config.id
        assert not set(config.configure) & set(config.common), config.id


def test_only_the_plug_configuration_does_not_build_a_compiler():
    """It is the row that matters most. A plugin that only loads into a compiler we built
    ourselves is a plugin that does not work."""
    assert [c.id for c in FOUND.configs if not c.from_source] == ["plug"]
    assert FOUND["plug"].flags == []
    assert FOUND["plug"].dockerfile == "Dockerfile.plug"


def test_the_bootstrap_is_the_one_that_never_runs_on_a_push():
    """Four hours per architecture is not something to spend on a typo fix."""
    assert [c.id for c in FOUND.configs if not c.on_patches] == ["boot"]
    assert FOUND["boot"].make == "bootstrap"


def test_a_cross_compiler_installs_and_smoke_tests_differently_from_a_native_one():
    """`install-strip` has nothing to strip after `all-gcc`, and there is no libc to link."""
    cross = FOUND["cross"]
    assert cross.make == "all-gcc"
    assert cross.install == "install-gcc"
    assert " -c " in cross.smoke
    assert cross.smoke.startswith("riscv64-unknown-elf-gcc")


def test_a_cross_compiler_brings_its_own_assembler():
    """The first run of this matrix built the compiler and then could not assemble with it.
    GCC falls back to the host `as`, which says `unknown architecture rv64gc` and reads like
    a GCC bug rather than a missing package."""
    cross = FOUND["cross"]
    assert "binutils-riscv64-unknown-elf" in cross.packages
    assert cross.packages != ""


def test_the_triple_and_the_binutils_package_name_agree():
    """GCC looks for `<target>-as` by that exact name. A target of riscv64-elf with binutils
    packaged as riscv64-unknown-elf finds nothing, and finds it silently."""
    cross = FOUND["cross"]
    (target,) = [f.split("=", 1)[1] for f in cross.configure if f.startswith("--target=")]
    assert f"binutils-{target}" == cross.packages
    assert cross.smoke.startswith(f"{target}-gcc")


def test_a_cross_compiler_names_its_assembler_and_linker_outright():
    """Installing the package is not enough, which cost a second round trip to learn. The
    driver searches its own prefix for the tools and the distribution installs them under
    another one, so it silently falls back to the host `as`."""
    cross = FOUND["cross"]
    named = {f.split("=", 1)[0] for f in cross.configure}
    assert "--with-as" in named
    assert "--with-ld" in named
    for flag in cross.configure:
        if flag.startswith(("--with-as=", "--with-ld=")):
            assert flag.split("=", 1)[1].startswith("/"), flag


def test_only_the_cross_compiler_asks_for_extra_packages():
    """Everything else belongs in the shared base, where it is installed once."""
    assert [c.id for c in FOUND.configs if c.packages] == ["cross"]


def test_the_matrix_is_pinned_to_the_same_gcc_the_citations_resolve_against():
    """A lesson that cites 16.2.0 and runs against 16.3.0 is wrong in a way nothing sees."""
    from tools.refcheck import PINNED_TAG

    assert FOUND.tag == PINNED_TAG


def test_a_weekly_run_is_every_configuration_on_both_architectures():
    jobs = FOUND.jobs("weekly")
    assert len(jobs) == len(FOUND.configs) * len(matrix.ARCHES)
    assert {j["runner"] for j in jobs} == {"ubuntu-24.04", "ubuntu-24.04-arm"}


def test_a_push_run_is_everything_except_the_bootstrap():
    jobs = FOUND.jobs("push")
    assert "boot" not in {j["id"] for j in jobs}
    assert len(jobs) == (len(FOUND.configs) - 1) * len(matrix.ARCHES)


def test_a_job_carries_everything_the_build_needs_and_nothing_it_has_to_look_up():
    (job,) = [j for j in FOUND.jobs("weekly") if j["id"] == "chk" and j["arch"] == "amd64"]
    assert job["image"] == "ghcr.io/tamnd/gcc-internals/chk:amd64"
    assert "--enable-checking=all,rtl,extra" in job["flags"]
    assert job["cflags"] == "-O0 -g"
    assert job["install"] == "install-strip"


def test_asking_for_a_trigger_that_does_not_exist_says_so():
    with pytest.raises(matrix.MatrixError, match="no 'nightly' trigger"):
        FOUND.jobs("nightly")


def test_asking_for_a_configuration_that_does_not_exist_lists_the_ones_that_do():
    with pytest.raises(matrix.MatrixError, match="rel, chk, dbg"):
        FOUND["lto"]


def test_an_architecture_with_no_runner_is_an_error_and_not_a_guess():
    with pytest.raises(matrix.MatrixError, match="no 'ppc64le' runner"):
        matrix.runner("ppc64le")


def test_a_configuration_built_on_a_push_but_never_on_a_schedule_is_rejected(tmp_path):
    """It goes stale the month nobody touches patches, and then it is two releases behind."""
    path = write(tmp_path, ONE.replace("weekly = true", "weekly = false"))
    with pytest.raises(matrix.MatrixError, match="never on a schedule"):
        matrix.load(path)


def test_a_configuration_that_builds_gcc_and_never_checks_it_works_is_rejected(tmp_path):
    """Four hours is a long time to spend producing a compiler nobody ran."""
    path = write(tmp_path, ONE.replace('smoke = "gcc -O2 /tmp/t.c -o /tmp/t"', 'smoke = ""'))
    with pytest.raises(matrix.MatrixError, match="never checks that it works"):
        matrix.load(path)


def test_a_configuration_that_builds_gcc_and_never_installs_it_is_rejected(tmp_path):
    path = write(tmp_path, ONE.replace('install = "install-strip"', 'install = ""'))
    with pytest.raises(matrix.MatrixError, match="never installs it"):
        matrix.load(path)


def test_the_same_id_twice_is_caught(tmp_path):
    path = write(tmp_path, ONE + ONE.split("[[config]]")[1].join(["[[config]]", ""]))
    with pytest.raises(matrix.MatrixError, match="in here twice"):
        matrix.load(path)


def test_a_configuration_for_no_architecture_is_caught(tmp_path):
    path = write(tmp_path, ONE.replace('arches = ["amd64"]', "arches = []"))
    with pytest.raises(matrix.MatrixError, match="no architecture at all"):
        matrix.load(path)


def test_the_committed_table_is_the_one_the_generator_writes():
    assert matrix.table(FOUND) in matrix.README.read_text(encoding="utf-8")
    assert matrix.build() is False


def test_the_table_says_how_many_machine_hours_a_weekly_run_costs():
    """A number nobody has written down is a number nobody notices doubling."""
    assert f"{FOUND.hours} machine hours" in matrix.table(FOUND)
    assert FOUND.hours > 0


def test_a_readme_with_no_markers_says_so_rather_than_writing_nothing():
    with pytest.raises(matrix.MatrixError, match="markers"):
        matrix.rewrite("# no markers here\n", "table")


def test_the_lockfile_is_read_even_when_it_is_empty(tmp_path):
    """A lockfile with no images in it is a state, not a crash.

    It is what a fresh clone of this project would have before the first matrix run
    publishes anything, and `digests` has to return an empty mapping rather than raise.
    Written against a temporary file and not the committed one, because the committed one
    stopped being empty the moment the matrix first published and a test that reads it is
    a test that expires.
    """
    empty = tmp_path / "images.lock.json"
    empty.write_text('{"images": {}}', encoding="utf-8")
    assert matrix.digests(empty) == {}


def test_a_lockfile_that_is_not_there_at_all_is_also_not_a_crash(tmp_path):
    assert matrix.digests(tmp_path / "nothing.json") == {}


def test_the_committed_lockfile_is_readable_and_pins_by_digest():
    """Whatever is in it, every entry has to be a digest.

    This is the half of the lockfile check that can run without knowing whether a full
    weekly run has happened yet. `lock_problems` is the half that knows, and issue #61 is
    about making it blocking once all twelve images exist.
    """
    for name, digest in matrix.digests().items():
        assert digest.startswith("sha256:"), name
        assert len(digest) == len("sha256:") + 64, name


def test_an_image_the_matrix_no_longer_builds_is_the_dangerous_one():
    """That digest keeps resolving forever, so a job goes on pulling a compiler nothing
    rebuilds, and nothing anywhere says so."""
    stale = {"ghcr.io/tamnd/gcc-internals/lto:amd64": "sha256:" + "a" * 64}
    problems = matrix.lock_problems(FOUND, stale)
    assert any("lto:amd64 is in the lockfile and not in the matrix" in p for p in problems)


def test_something_that_is_not_a_digest_is_not_accepted_as_one():
    """A tag looks like a pin and is not one. It moves, and that is the whole problem."""
    problems = matrix.lock_problems(FOUND, {"ghcr.io/tamnd/gcc-internals/rel:amd64": "latest"})
    assert any("is not a digest" in p for p in problems)


def test_recording_a_run_merges_rather_than_replaces(tmp_path):
    """A run that rebuilt one configuration by hand must not delete the other eleven."""
    lock = tmp_path / "images.lock.json"
    lock.write_text(
        json.dumps({"images": {"ghcr.io/x/chk:amd64": "sha256:" + "b" * 64}}), encoding="utf-8"
    )
    incoming = tmp_path / "digests"
    incoming.mkdir()
    (incoming / "rel-amd64.txt").write_text(
        "ghcr.io/x/rel:amd64 sha256:" + "c" * 64 + "\n", encoding="utf-8"
    )
    have = matrix.record(incoming, lock)
    assert set(have) == {"ghcr.io/x/chk:amd64", "ghcr.io/x/rel:amd64"}
    assert list(json.loads(lock.read_text())["images"]) == sorted(have)


def test_a_digest_file_with_no_digest_in_it_is_an_error(tmp_path):
    """docker/build-push-action leaves the output empty when a push did not happen, and a
    lockfile entry pointing at nothing is worse than a missing one."""
    incoming = tmp_path / "digests"
    incoming.mkdir()
    (incoming / "rel-amd64.txt").write_text("ghcr.io/x/rel:amd64 \n", encoding="utf-8")
    with pytest.raises(matrix.MatrixError, match="no digest"):
        matrix.record(incoming, tmp_path / "images.lock.json")


def test_the_workflow_builds_the_configurations_this_file_describes():
    """The point of the whole exercise. The workflow asks, it does not know."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m tools.matrix jobs --on" in text
    assert "fromJSON(needs.plan.outputs.jobs)" in text
    for flag in ("--enable-checking=all,rtl,extra", "riscv64-unknown-elf"):
        assert flag not in text, "a configure flag belongs in matrix.toml and nowhere else"
    assert FOUND.tag not in text, "the pinned tag belongs in matrix.toml and nowhere else"


def test_the_workflow_hands_the_build_every_argument_a_dockerfile_takes():
    """A build arg the workflow forgets is a build arg that silently takes its default, and
    the default is `rel`, so `dbg` would publish an optimized compiler under the dbg name."""
    text = WORKFLOW.read_text(encoding="utf-8")
    declared = {
        line.split()[1].split("=")[0]
        for path in ("Dockerfile", "Dockerfile.plug")
        for line in (matrix.CONTAINERS / path).read_text(encoding="utf-8").splitlines()
        if line.startswith("ARG ")
    }
    for name in declared - {"CFLAGS"}:
        assert f"{name}=" in text, name


def test_a_pull_request_builds_the_images_and_does_not_publish_them():
    """Otherwise a branch anybody can open replaces the compiler main tests against."""
    text = WORKFLOW.read_text(encoding="utf-8")
    plan = yaml.safe_load(text)["jobs"]["plan"]["steps"][-1]["run"]
    assert "publish=false" in plan
    assert "pull_request" in plan


def test_the_workflow_is_the_only_place_that_builds_a_compiler():
    """The rule the whole build caching story rests on, checked rather than intended."""
    others = [
        path
        for path in (matrix.REPO_ROOT / ".github" / "workflows").glob("*.yml")
        if path != WORKFLOW
    ]
    assert others
    for path in others:
        text = path.read_text(encoding="utf-8")
        assert "containers/Dockerfile" not in text, path.name
        assert "gcc/configure" not in text, path.name
