"""Manager display-name aliasing (config/aliases.json).

Managers rename themselves on Sleeper between seasons. Without a resolver the same
person splits into two identities across All-Time, Head-to-Head and Hall of Fame,
and the failure is silent — lookups fall through to sentinels rather than raising.
These tests guard every surface where a manager name enters the system.
"""

import json
import os

import pytest

import sleeper_core as core


# Names that existed in the config before the 2026 rename and must no longer
# appear anywhere in loaded data.
LEGACY_NAMES = {"jhuntmadd", "InfiniteJesse"}


class TestCanonicalName:
    def test_maps_known_alias(self):
        assert core.canonical_name("jhuntmadd") == "jhmad"
        assert core.canonical_name("InfiniteJesse") == "InfiniteJess"

    def test_passes_through_unknown(self):
        assert core.canonical_name("bgmaddox") == "bgmaddox"

    def test_idempotent(self):
        for name in ["jhuntmadd", "jhmad", "InfiniteJesse", "bgmaddox", ""]:
            once = core.canonical_name(name)
            assert core.canonical_name(once) == once, name

    def test_non_string_passthrough(self):
        """Callers apply this to raw API/config values without pre-filtering."""
        assert core.canonical_name(None) is None
        assert core.canonical_name(7) == 7

    def test_no_alias_target_is_itself_an_alias_key(self):
        """A -> B -> C chain would make resolution order-dependent."""
        targets = set(core.NAME_ALIASES.values())
        assert not (targets & set(core.NAME_ALIASES)), \
            "alias targets must be canonical, not themselves aliased"


class TestCanonicalNamesStr:
    def test_compound_winner(self):
        assert core.canonical_names_str("jhuntmadd & BMoreBallers88") == "jhmad & BMoreBallers88"

    def test_three_way_winner(self):
        assert core.canonical_names_str(
            "BMoreBallers88 & RReclam & jhuntmadd"
        ) == "BMoreBallers88 & RReclam & jhmad"

    def test_single_name_unchanged_shape(self):
        assert core.canonical_names_str("bgmaddox") == "bgmaddox"

    def test_empty_and_non_string(self):
        assert core.canonical_names_str("") == ""
        assert core.canonical_names_str(None) is None


class TestLoadedConfigIsCanonical:
    def test_no_legacy_names_in_roster_ids(self):
        found = [(y, slot, name)
                 for y, slots in core.roster_ids.items()
                 for slot, name in slots.items()
                 if name in LEGACY_NAMES]
        assert not found, f"legacy names survived in roster_ids: {found}"

    def test_no_legacy_names_in_side_bet_winners(self):
        found = [(y, wk, cfg["winner"])
                 for y, weeks in core.SIDE_BET_SEASONS.items()
                 for wk, cfg in weeks.items()
                 if any(legacy in cfg["winner"] for legacy in LEGACY_NAMES)]
        assert not found, f"legacy names survived in side bet winners: {found}"

    def test_alias_file_keys_are_not_canonical_names(self):
        """An alias key that's also a current roster name would rewrite a real manager."""
        current = set(core.roster_ids[max(core.roster_ids)].values())
        overlap = current & set(core.NAME_ALIASES)
        assert not overlap, f"alias keys collide with current managers: {overlap}"

    def test_alias_targets_are_real_managers(self):
        """Guards against a typo in aliases.json silently creating a phantom manager."""
        everyone = {n for slots in core.roster_ids.values() for n in slots.values()}
        unknown = set(core.NAME_ALIASES.values()) - everyone
        assert not unknown, f"alias targets not present in any season roster: {unknown}"


class TestAliasesFile:
    def test_file_parses_and_ignores_comment_keys(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "aliases.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        assert any(k.startswith("_") for k in raw), "expected a _comment key in aliases.json"
        assert not any(k.startswith("_") for k in core.NAME_ALIASES), \
            "underscore-prefixed keys must be stripped when loading"


class TestAllTimeIdentityMerge:
    def test_renamed_managers_are_single_identity(self):
        """The whole point: 12 managers in 2026, and the renamed pair isn't doubled."""
        everyone = {n for slots in core.roster_ids.values() for n in slots.values()}
        assert "jhmad" in everyone and "jhuntmadd" not in everyone
        assert "InfiniteJess" in everyone and "InfiniteJesse" not in everyone

    def test_renamed_managers_keep_distinct_alltime_colors(self):
        colors = core.get_alltime_teamcolors()
        assert len(set(colors.values())) == len(colors), "all-time colors must be unique"
        assert colors["jhmad"] != colors["InfiniteJess"]
