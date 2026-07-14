"""
Playoffs feature tests — Tasks 3A, 4A, 4B.

Organized in three groups:
  TestBreakoutPlayerID  — 3A: player_id column in dfBreakout (should pass now)
  TestBracketFetchers   — 4A: fetch_winners/losers_bracket (should pass now)
  TestPlayoffsClass     — 4B: Playoffs class in sleeper_core (xfail until implemented)

All tests load from .cache/ — no API calls made during the run.
"""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import data_loader as dl
import sleeper_core as core


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def league_2024_playoffs():
    """League and Season objects for 2024, used by Playoffs tests."""
    path = dl._cache_path("season_data_2024_18")
    if not os.path.exists(path):
        pytest.skip("2024 cache not found — start the app once to build it")
    league, season, _ = dl.load_data_for_year(2024, verbose=False)
    return league, season


@pytest.fixture(scope="module")
def breakout_2024():
    """Flat DataFrame of all 2024 dfBreakout weeks concatenated."""
    import pandas as pd
    path = dl._cache_path("season_data_2024_18")
    if not os.path.exists(path):
        pytest.skip("2024 cache not found — start the app once to build it")
    dl.load_data_for_year(2024, verbose=False)
    frames = list(core.AllBreakoutDict[2024].values())
    assert frames, "AllBreakoutDict[2024] is empty"
    return pd.concat(frames, ignore_index=True)


# ── 3A: player_id in dfBreakout ───────────────────────────────────────────────

class TestBreakoutPlayerID:

    def test_breakout_has_player_id_column(self, breakout_2024):
        assert 'player_id' in breakout_2024.columns, \
            "dfBreakout is missing player_id column — Task 3A not applied"

    def test_player_id_not_all_null(self, breakout_2024):
        null_count = breakout_2024['player_id'].isna().sum()
        total = len(breakout_2024)
        assert null_count < total, "All player_id values are null"

    def test_player_id_is_string_for_known_players(self, breakout_2024):
        # Non-null player_ids should be strings (Sleeper uses string IDs)
        non_null = breakout_2024['player_id'].dropna()
        assert pd.api.types.is_string_dtype(non_null), \
            "player_id column should be string dtype (object or StringDtype)"

    def test_player_id_majority_populated(self, breakout_2024):
        # Most rows should have a player_id. Allows for DEF rows and name-match
        # misses in older caches. After a fresh cache rebuild post-3A, coverage
        # should approach 100% since Sleeper IDs are set before any merges.
        non_null_pct = breakout_2024['player_id'].notna().mean()
        assert non_null_pct > 0.75, \
            f"Only {non_null_pct:.0%} of rows have a player_id — expected >75%"


# ── 4A: bracket fetchers ──────────────────────────────────────────────────────

class TestBracketFetchers:

    def test_fetch_winners_bracket_returns_list(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        assert isinstance(result, list), "fetch_winners_bracket should return a list"

    def test_fetch_losers_bracket_returns_list(self):
        result = dl.fetch_losers_bracket(core.leagueID_2025)
        assert isinstance(result, list), "fetch_losers_bracket should return a list"

    def test_winners_bracket_has_entries(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        assert len(result) > 0, "Winners bracket is empty"

    def test_losers_bracket_has_entries(self):
        result = dl.fetch_losers_bracket(core.leagueID_2025)
        assert len(result) > 0, "Losers bracket is empty"

    def test_winners_bracket_has_three_rounds(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        rounds = {m['r'] for m in result}
        assert rounds == {1, 2, 3}, f"Expected rounds {{1,2,3}}, got {rounds}"

    def test_losers_bracket_has_three_rounds(self):
        result = dl.fetch_losers_bracket(core.leagueID_2025)
        rounds = {m['r'] for m in result}
        assert rounds == {1, 2, 3}, f"Expected rounds {{1,2,3}}, got {rounds}"

    def test_winners_bracket_match_count_for_6_teams(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        assert len(result) == 7, \
            f"6-team bracket should have 7 matches, got {len(result)}"

    def test_bracket_entries_have_required_keys(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        required = {'r', 'm', 't1', 't2'}
        for entry in result:
            missing = required - set(entry.keys())
            assert not missing, f"Bracket entry missing keys {missing}: {entry}"

    def test_settled_bracket_has_no_null_winners(self):
        # 2025 is a completed season — all w/l fields should be filled
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        for entry in result:
            assert entry.get('w') is not None, \
                f"Match {entry['m']} has null winner in settled bracket"
            assert entry.get('l') is not None, \
                f"Match {entry['m']} has null loser in settled bracket"

    def test_championship_match_has_placement_1(self):
        result = dl.fetch_winners_bracket(core.leagueID_2025)
        champ_matches = [m for m in result if m.get('p') == 1]
        assert len(champ_matches) == 1, \
            f"Expected exactly 1 championship match (p=1), got {len(champ_matches)}"


# ── 4B: Playoffs class ────────────────────────────────────────────────────────

WINNERS_REQUIRED_KEYS = {'match', 'team1', 'score1', 'team2', 'score2', 'winner',
                          'placement', 'best_player', 'bench_left'}
LOSERS_REQUIRED_KEYS  = {'match', 'team1', 'score1', 'team2', 'score2', 'winner',
                          'placement'}


class TestPlayoffsClass:

    def test_playoffs_class_exists(self, league_2024_playoffs):
        assert hasattr(core, 'Playoffs'), "core.Playoffs class does not exist"

    def test_playoffs_instantiates(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert playoffs is not None

    def test_playoff_week_start_from_league_settings(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        # Must come from the API, not be hardcoded — value should be 15 for this league
        assert hasattr(playoffs, 'playoff_week_start'), \
            "Playoffs missing playoff_week_start attribute"
        assert isinstance(playoffs.playoff_week_start, int)
        assert playoffs.playoff_week_start == 15

    def test_playoffs_has_winners_attribute(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert hasattr(playoffs, 'winners'), "Playoffs missing 'winners' attribute"
        assert isinstance(playoffs.winners, dict)

    def test_playoffs_has_losers_attribute(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert hasattr(playoffs, 'losers'), "Playoffs missing 'losers' attribute"
        assert isinstance(playoffs.losers, dict)

    def test_winners_has_three_rounds(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert set(playoffs.winners.keys()) == {1, 2, 3}, \
            f"Winners bracket should have rounds 1-3, got {set(playoffs.winners.keys())}"

    def test_losers_has_three_rounds(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert set(playoffs.losers.keys()) == {1, 2, 3}, \
            f"Losers bracket should have rounds 1-3, got {set(playoffs.losers.keys())}"

    def test_winners_round1_has_two_matchups(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert len(playoffs.winners[1]) == 2, \
            f"Round 1 should have 2 wild card games, got {len(playoffs.winners[1])}"

    def test_winners_round2_has_three_matchups(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        assert len(playoffs.winners[2]) == 3, \
            f"Round 2 should have 3 games (2 semis + 5th place), got {len(playoffs.winners[2])}"

    def test_winners_matchups_have_required_keys(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                missing = WINNERS_REQUIRED_KEYS - set(m.keys())
                assert not missing, \
                    f"Winners round {rnd} matchup missing keys: {missing}"

    def test_losers_matchups_have_required_keys(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.losers.items():
            for m in matchups:
                missing = LOSERS_REQUIRED_KEYS - set(m.keys())
                assert not missing, \
                    f"Losers round {rnd} matchup missing keys: {missing}"

    def test_scores_are_numeric(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert isinstance(m['score1'], (int, float)), \
                    f"score1 is not numeric in round {rnd}: {m['score1']}"
                assert isinstance(m['score2'], (int, float)), \
                    f"score2 is not numeric in round {rnd}: {m['score2']}"

    def test_scores_are_nonzero(self, league_2024_playoffs):
        # Settled brackets should have real scores, not placeholder zeros
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert m['score1'] > 0, f"score1 is 0 in round {rnd} match {m['match']}"
                assert m['score2'] > 0, f"score2 is 0 in round {rnd} match {m['match']}"

    def test_team_names_are_strings_not_roster_ids(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        valid_team_names = set(core.roster_ids[2024].values())
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert m['team1'] in valid_team_names, \
                    f"team1 '{m['team1']}' is not a known team name (round {rnd})"
                assert m['team2'] in valid_team_names, \
                    f"team2 '{m['team2']}' is not a known team name (round {rnd})"

    def test_winner_field_matches_a_team(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert m['winner'] in (m['team1'], m['team2']), \
                    f"winner '{m['winner']}' is not team1 or team2 in round {rnd}"

    def test_championship_matchup_has_placement_1(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        champ = [m for m in playoffs.winners[3] if m.get('placement') == 1]
        assert len(champ) == 1, "Expected exactly one championship matchup (placement=1)"

    def test_best_player_is_string(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert isinstance(m['best_player'], str), \
                    f"best_player should be a string in round {rnd}: {m['best_player']}"
                assert len(m['best_player']) > 0, \
                    f"best_player is empty string in round {rnd}"

    def test_bench_left_is_numeric(self, league_2024_playoffs):
        league, season = league_2024_playoffs
        playoffs = core.Playoffs(league, season)
        for rnd, matchups in playoffs.winners.items():
            for m in matchups:
                assert isinstance(m['bench_left'], (int, float)), \
                    f"bench_left should be numeric in round {rnd}: {m['bench_left']}"
