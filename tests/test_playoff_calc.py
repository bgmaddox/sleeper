# tests/test_playoff_calc.py
# Session 9 regression tests: Playoff Calculator semantics + presentation honesty.
#
# Covers:
#   - played games in as_of_week fold into standings (not discarded)
#   - retroactive checkpoints yield real probabilities, not 0%/100% step functions
#   - rematch pairs can't blow up the swing-tally indexing
#   - tie handling (0.5 wins each, both in the fold and in Week's Won column)
#   - lineup-slots-vs-league-settings validation

import warnings

import numpy as np
import pandas as pd
import pytest

import sleeper_core as core
import data_loader as dl


def _bare_calc():
    """PlayoffCalculator instance without League/Season — for pure-math methods."""
    return object.__new__(core.PlayoffCalculator)


class TestFoldPlayedResults:
    def _standings(self):
        return {
            1: {'wins': 5, 'losses': 4, 'points_for': 1000.0, 'name': 'a'},
            2: {'wins': 4, 'losses': 5, 'points_for': 900.0, 'name': 'b'},
        }

    def test_win_and_loss_folded(self):
        s = self._standings()
        core.PlayoffCalculator._fold_played_results(s, [(1, 120.0, 2, 100.0)])
        assert s[1]['wins'] == 6 and s[1]['losses'] == 4
        assert s[2]['wins'] == 4 and s[2]['losses'] == 6
        assert s[1]['points_for'] == 1120.0
        assert s[2]['points_for'] == 1000.0

    def test_tie_gives_half_win_each(self):
        s = self._standings()
        core.PlayoffCalculator._fold_played_results(s, [(1, 110.0, 2, 110.0)])
        assert s[1]['wins'] == 5.5 and s[1]['losses'] == 4.5
        assert s[2]['wins'] == 4.5 and s[2]['losses'] == 5.5

    def test_unknown_roster_id_ignored(self):
        s = self._standings()
        core.PlayoffCalculator._fold_played_results(s, [(1, 120.0, 99, 100.0)])
        assert s[1]['wins'] == 6
        assert 99 not in s


class TestRematchGuard:
    def test_exact_numpy_survives_rematch_pair(self):
        # Same (a, b) tuple appears in the current week AND a later week.
        # Under the old tuple-identity mapping this indexed swing_tally out of
        # bounds; the positional prefix mapping must handle it.
        calc = _bare_calc()
        matchup_pairs = [(1, 2), (3, 4), (1, 2), (3, 4)]  # weeks: cw, cw, later, later
        current_week_pairs = [(1, 2), (3, 4)]
        initial_wins = {1: 5, 2: 4, 3: 3, 4: 2}
        pf = {1: 1000.0, 2: 950.0, 3: 900.0, 4: 850.0}
        in_count, guar_count, num_sims, swing_tally, swing_count = calc._exact_numpy(
            matchup_pairs, current_week_pairs, initial_wins, pf,
            num_playoffs=2, total_scenarios=2 ** len(matchup_pairs))
        assert num_sims == 16
        assert swing_tally.shape == (4, 2, 2)
        # every scenario counted exactly once per current-week game
        assert (swing_count.sum(axis=1) == 16).all()

    def test_probabilities_sum_to_playoff_spots(self):
        calc = _bare_calc()
        matchup_pairs = [(1, 2), (3, 4)]
        current_week_pairs = [(1, 2)]
        initial_wins = {1: 5, 2: 5, 3: 5, 4: 5}
        pf = {1: 1000.0, 2: 990.0, 3: 980.0, 4: 970.0}
        in_count, _, num_sims, _, _ = calc._exact_numpy(
            matchup_pairs, current_week_pairs, initial_wins, pf,
            num_playoffs=2, total_scenarios=4)
        # exactly num_playoffs teams make it in every scenario
        assert in_count.sum() == 2 * num_sims


class TestRetroactiveCheckpoints:
    def test_week10_checkpoint_is_probabilistic_not_binary(self, season_2024):
        league, season, weeks = season_2024
        calc = core.PlayoffCalculator(league, season, 10)
        snaps = calc.compute()
        assert len(snaps) == 12
        probs = [s.prob_any for s in snaps]
        assert all(0.0 <= p <= 1.0 for p in probs)
        # The old bug collapsed every retroactive checkpoint to {0, 1}.
        assert any(0.0 < p < 1.0 for p in probs), \
            "retroactive checkpoint is a 0/100 step function again"
        # exactly 6 playoff spots' worth of probability mass
        assert sum(probs) == pytest.approx(6.0, abs=0.01)

    def test_checkpoint_wins_include_as_of_week_results(self, season_2024):
        league, season, weeks = season_2024
        calc = core.PlayoffCalculator(league, season, 10)
        snaps = calc.compute()
        m = pd.concat([core.AllMatchesDict[2024][w] for w in range(1, 11)])
        m = m[m['Season'] == 'Regular']
        truth = m.groupby('Team')['Won'].sum().to_dict()
        for s in snaps:
            assert s.wins == truth[s.name], \
                f"{s.name}: checkpoint wins {s.wins} != through-week-10 record {truth[s.name]}"

    def test_final_week_checkpoint_is_deterministic(self, season_2024):
        # After the last regular-season week everything is decided: 0/1 only.
        league, season, weeks = season_2024
        playoff_start = int(league.league_settings.get('settings.playoff_week_start', 15))
        calc = core.PlayoffCalculator(league, season, playoff_start - 1)
        snaps = calc.compute()
        assert all(s.prob_any in (0.0, 1.0) for s in snaps)
        assert sum(s.prob_any for s in snaps) == 6.0


class TestTieHandling:
    def test_historical_won_column_still_integral(self, season_2024):
        # No tie has occurred in league history: the Won column must be
        # unchanged (0/1 only) by the tie-handling insurance.
        for week, df in core.AllMatchesDict[2024].items():
            assert set(df['Won'].unique()) <= {0, 1}

    def test_one_win_per_matchup(self, season_2024):
        for week, df in core.AllMatchesDict[2024].items():
            reg = df[df['Season'] == 'Regular']
            per_matchup = reg.groupby('Matchup')['Won'].sum()
            assert (per_matchup == 1).all(), f"week {week}: a matchup awarded != 1 total win"


class TestLineupSlotValidation:
    GOOD = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF', 'BN', 'BN']

    def test_matching_settings_no_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            core.validate_lineup_slots({'roster_positions': self.GOOD}, 2024)

    def test_mismatched_settings_warn(self):
        bad = self.GOOD + ['WR']  # 3 WRs
        with pytest.warns(UserWarning, match='differ from the hardcoded'):
            core.validate_lineup_slots({'roster_positions': bad}, 2024)

    def test_missing_key_is_silent(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            core.validate_lineup_slots({}, 2024)

    def test_all_cached_seasons_match_hardcoded_slots(self, season_2024):
        league, _, _ = season_2024
        positions = league.league_settings.get('roster_positions')
        starters = [p for p in positions if p not in ('BN', 'IR', 'TAXI')]
        counts = {}
        for p in starters:
            counts[p] = counts.get(p, 0) + 1
        assert counts == core.LINEUP_SLOTS


class TestLoadPlayoffProbs:
    def test_cache_key_versioned(self):
        import inspect
        src = inspect.getsource(dl.load_playoff_probs)
        assert 'playoff_probs_v2_' in src, "cache key must be versioned past v1 semantics"
