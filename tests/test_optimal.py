"""
Optimal-lineup family regression tests (fix roadmap Session 3).

Reference values come from the Phase 6 analysis-soundness review:
independently computed optimal lineups for 2023 Week 5
(QB1/RB2/WR2/TE1/FLEX1/K1/DEF1, deduped by player_id).

Guards against:
- the FLEX-by-NFL-team bug in Week.OptimalTeams (wrong scores for 11/12 teams)
- the pooled-flex overcount (top-6 RB/WR/TE ignores positional limits)
- LineupEfficiency > 100% (week_NFL filter dropped all DEF from the optimal)
- the LuckChart horizontal divider drawn at the wrong median
"""
import os
import pytest
import data_loader as dl
import sleeper_core as core


# Phase 6 reference optimal scores, 2023 Week 5
REFERENCE_OPTIMAL_2023_W5 = {
    'RascalHazard': 107.44,
    'bgmaddox': 116.10,
    'JTizzzzle': 104.16,
    'jhuntmadd': 175.78,
    'eegrady': 91.02,
    'RossLikeSauce': 87.28,
}

# QB1/RB2/WR2/TE1/K1/DEF1 + FLEX1
LINEUP_SIZE = 9
MAX_AT_POSITION = {'QB': 1, 'K': 1, 'DEF': 1, 'RB': 3, 'WR': 3, 'TE': 2}


@pytest.fixture(scope="module")
def season_2023():
    path = dl._cache_path("season_data_2023_18")
    if not os.path.exists(path):
        pytest.skip("2023 cache not found — start the app once to build it")
    return dl.load_data_for_year(2023, verbose=False)


@pytest.fixture(scope="module")
def week5_2023(season_2023):
    _, _, weeks = season_2023
    wk = weeks[5]
    wk.OptimalTeams()
    return wk


class TestWeekOptimalTeams:

    def test_matches_phase6_reference(self, week5_2023):
        for team, expected in REFERENCE_OPTIMAL_2023_W5.items():
            got = week5_2023.OptimalScoresDict[team]
            assert abs(got - expected) < 0.01, f"{team}: expected {expected}, got {got}"

    def test_all_teams_present(self, week5_2023):
        assert len(week5_2023.OptimalScoresDict) == 12

    def test_lineups_are_legal(self, week5_2023):
        df = week5_2023.OptimalScoresDF
        for team, lineup in df.groupby('team'):
            assert len(lineup) == LINEUP_SIZE, f"{team}: {len(lineup)} players, expected {LINEUP_SIZE}"
            counts = lineup['position'].value_counts()
            for pos, cap in MAX_AT_POSITION.items():
                assert counts.get(pos, 0) <= cap, f"{team}: {counts.get(pos, 0)} {pos}s exceeds max {cap}"

    def test_no_duplicate_players_in_lineup(self, week5_2023):
        df = week5_2023.OptimalScoresDF
        dupes = df.duplicated(subset=['team', 'player_id']).sum()
        assert dupes == 0, f"{dupes} duplicate players in optimal lineups"

    def test_optimal_at_least_actual(self, season_2023, week5_2023):
        _, season, _ = season_2023
        actuals = season.Matches[season.Matches['Week'] == 5].set_index('Team')['Total']
        for team, actual in actuals.items():
            optimal = week5_2023.OptimalScoresDict[team]
            assert optimal >= actual - 0.01, f"{team}: optimal {optimal} < actual {actual}"

    def test_luckscore_dead_code_removed(self, week5_2023):
        assert not hasattr(week5_2023, 'LuckScore'), "Week.LuckScore was dead code and should stay deleted"


class TestLineupEfficiency:

    def test_efficiency_never_exceeds_100(self, season_2023):
        _, season, _ = season_2023
        for week in (1, 5, 10):
            df = season.LineupEfficiency(week)
            assert not df.empty
            over = df[df['Efficiency'] > 1.0 + 1e-9]
            assert over.empty, f"Week {week}: efficiency > 100% for {over['Team'].tolist()}"

    def test_agrees_with_week_optimal(self, season_2023, week5_2023):
        _, season, _ = season_2023
        eff = season.LineupEfficiency(5).set_index('Team')
        for team, optimal in week5_2023.OptimalScoresDict.items():
            assert abs(eff.loc[team, 'Optimal'] - optimal) < 0.01, (
                f"{team}: LineupEfficiency optimal {eff.loc[team, 'Optimal']} "
                f"!= Week.OptimalTeams {optimal}"
            )

    def test_includes_def_in_optimal(self, season_2023):
        _, season, _ = season_2023
        bs = season.BreakoutSeason
        week_data = bs[bs['week_x'] == 5]
        assert (week_data['position'] == 'DEF').any(), "week_x slice should retain DEF rows"


class TestLuckChart:

    def test_horizontal_divider_at_median_points_for(self, season_2023):
        _, season, _ = season_2023
        fig = season.LuckChart(5)
        df_week = season.ConcatinatedWeeks[season.ConcatinatedWeeks['Week'] == 5]
        median_score = df_week['Score YTD'].median()
        median_opp = df_week['Opp YTD'].median()
        horizontal = [s for s in fig.layout.shapes if s.y0 == s.y1]
        vertical = [s for s in fig.layout.shapes if s.x0 == s.x1]
        assert len(horizontal) == 1 and len(vertical) == 1
        assert abs(horizontal[0].y0 - median_score) < 0.01, "horizontal divider must sit at median Points For"
        assert abs(vertical[0].x0 - median_opp) < 0.01, "vertical divider must sit at median Points Against"


class TestSeasonCalc:

    def test_statusdict_has_correct_optimal(self, season_2023):
        _, season, weeks = season_2023
        season.Calc(weeks[5])
        opt = season.StatusDict['OptimalScores']
        for team, expected in REFERENCE_OPTIMAL_2023_W5.items():
            assert abs(opt[team] - expected) < 0.01


class TestSeasonOptimalTeams:

    def test_lineups_are_legal(self, season_2023):
        _, season, _ = season_2023
        season.OptimalTeams()
        for team, lineup in season.OptimalScoresDF.groupby('team'):
            counts = lineup['position'].value_counts()
            for pos, cap in MAX_AT_POSITION.items():
                assert counts.get(pos, 0) <= cap, f"{team}: {counts.get(pos, 0)} {pos}s exceeds max {cap}"
