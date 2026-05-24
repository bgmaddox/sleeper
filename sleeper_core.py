# sleeper_core.py
# Core data classes and Plotly template extracted from Sleeper_v2.ipynb
# Chart methods return figures (instead of calling fig.show()).

import os
import pandas as pd
import requests
from pandas import json_normalize
import json
import numpy as np
import re
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import Image
from sklearn.preprocessing import MinMaxScaler, StandardScaler
import nfl_data_py as nfl

pd.options.mode.copy_on_write = True

# ── League Logo ──────────────────────────────────────────────────────────────
_LOGO_URL = "https://raw.githubusercontent.com/bgmaddox/sleeper/master/LL%20logo.png"

def apply_logo_to_fig(fig, xval=0.5, yval=-0.05):
    return fig

# ── NFL Player Data ──────────────────────────────────────────────────────────
NFLPlayerData = {}   # populated lazily by init_player_data()

def init_player_data():
    global NFLPlayerData
    if not NFLPlayerData:
        import data_loader as dl
        NFLPlayerData = dl.fetch_player_data()

# ── Season configuration ──────────────────────────────────────────────────────
CURRENT_SEASON = 2025   # Update once per year when the new season begins

import plotly.io as pio

# 1. Define the color palette and fonts
ink_bg_color =  '#163146' #'#0D1B2A'
ink_text_color =  '#BDE2FF' #'#A9D6E5'
ink_grid_color =  '#3D5E78' #'#4A6B8A'
ink_secondary_color = '#8DCEFF'
ink_font = 'Courier New'
ink_colorway = ['#AAC49F','#FFBDF9','#234515', '#453215', '#451541', '#5B854A', '#C49FC1', '#C4B59F',
                '#854A7F', '#FFE5BD','#D0FFBD','#856D4A',]
coastal_colorway = [
    '#FFC300', # Gold Amber
    '#17BECF', # Vibrant Teal
    '#F94144', # Coral Red
    '#90BE6D', # Lime Green
    '#E377C2', # Bright Magenta
    '#54A2E5', # Sky Blue
    '#FF7F0E', # Bright Orange
    '#9467BD', # Muted Violet
    '#8C564B', # Muted Brown
    '#43AA8B', # Sea Green
    '#C5B0D5', # Light Lavender
    '#F0F0F0'  # Off-White/Silver
]

# Extended palette for all-time charts — first 12 match coastal_colorway (one per 2019 charter
# member), then unique colors for each player who joined later, plus extras for future expansion.
alltime_colorway = coastal_colorway + [
    '#FF1493', # Deep Pink       — jhuntmadd (joined 2020)
    '#ADFF2F', # Chartreuse      — RReclam (joined 2020)
    '#1E90FF', # Dodger Blue     — DirtyCommie (joined 2022)
    '#FF4500', # Orange Red      — sgmaddox (joined 2022)
    '#9932CC', # Dark Orchid     — Just_Here_For_The_Snacks (joined 2022)
    '#00FA9A', # Spring Green    — InfiniteJesse (joined 2023)
    '#E8A838', # Warm Amber      — cosmodromedary (joined 2025)
    '#00CED1', # Dark Turquoise  — future slot
    '#FF69B4', # Hot Pink        — future slot
    '#7CFC00', # Lawn Green      — future slot
    '#6495ED', # Cornflower Blue — future slot
    '#FFD700', # Pure Gold       — future slot
]

neon_future_colorway = [
    '#F92672', # Electric Pink
    '#66D9EF', # Vibrant Cyan
    '#A6E22E', # Lime Green
    '#FD971F', # Tangerine Orange
    '#AE81FF', # Rich Purple
    '#E6DB74', # Bright Yellow
    '#FF0000', # Classic Red
    '#529BFF', # Sky Blue
    '#50E3C2', # Seafoam Green
    '#FF6B00', # Hot Orange
    '#FFC0CB', # Light Pink
    '#F8F8F2', # Bright White
]

autumn_forest_colorway = [
    '#D95F02', # Burnt Orange
    '#1B9E77', # Forest Green
    '#E7A033', # Deep Gold
    '#D73027', # Maroon Red
    '#66A61E', # Olive Green
    '#7570B3', # Slate Blue
    '#008B8B', # Rich Teal
    '#FEC89A', # Muted Peach
    '#B35806', # Terracotta
    '#A1045A', # Plum Purple
    '#FEFAE0', # Warm Cream
    '#B0B0B0', # Cool Grey
]
# 2. Create a new template object
gridiron_ink_template = go.layout.Template()


# 3. Set the layout properties
gridiron_ink_template.layout = go.Layout(
    # --- Main Colors ---
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    barmode = 'group',
    # --- Fonts ---
    font=dict(family=ink_font, color=ink_text_color),
    font_family=ink_font,
    font_color=ink_text_color,
    # --- Hover labels ---
    hoverlabel=dict(
        bgcolor='#1a3a52',
        bordercolor='#2e526e',
        font=dict(family='Courier New', size=13, color='#BDE2FF'),
    ),
    title_font_family='Rockwell',
    title_font_color= '#FFC300', #ink_text_color,
    legend_title_font_color=ink_text_color,
    title=dict(
            font=dict(
                size=45,
                variant="petite-caps",
                shadow = 'auto'
            ),
            xanchor = 'center',
            yanchor = 'bottom',
            x= .50,
            y = .95,
            pad=dict(b=10,t=0,l=0,r=0),
            
            
            ),
    title_subtitle=dict(
            font=dict(
                size=30,
                #variant="small-caps",
                
            )),
    # --- Sizes ---
    height=1000,
    uniformtext_minsize=12,
    uniformtext_mode='hide',
    showlegend=False,

    # --- Axes ---
    xaxis=dict(
        side = 'top',
        gridcolor=ink_grid_color,
        linecolor=ink_grid_color,
        zerolinecolor=ink_secondary_color,
        zerolinewidth=3,
        tickfont=dict(
                size=20,
                    ),
         title_font=dict(
                    size=20,
                    shadow = 'auto',
                    color =ink_secondary_color
         ),
       title = dict(standoff = 5),
                  
    ),
    yaxis=dict(
        gridcolor=ink_grid_color,
        linecolor=ink_grid_color,
        zerolinecolor=ink_secondary_color,
        zerolinewidth=3,
        tickfont=dict(
                size=15,
                    ),
        title_font=dict(
                    size=20,
                    shadow='auto',
                    color=ink_secondary_color
         )                  
    ),
    
    # --- Data Colors ---
    colorway = coastal_colorway,
    
    # --- Legend ---
    legend=dict(
        bgcolor='rgba(26,58,82,0.85)',
        bordercolor='#2e526e',
        borderwidth=1,
        font=dict(family='Courier New', size=12, color='#BDE2FF'),
        orientation = 'h',
        yanchor="middle",
        y=1,
        xanchor="center",
        x=.5
    ),

    # --- Margins ---
    margin=dict(t=130, b=100, l= 80, r=40) ,# Add more space for a prominent title


)



gridiron_ink_template.data.bar = [
    go.Bar(
        marker=dict(
            cornerradius=13,
            line_color='#2C4C65', # You can add other marker properties here too
            line_width=3,
            
           ),
           insidetextanchor = 'middle',
           

    )
]


# 4. Register the new theme with Plotly
pio.templates['gridiron_ink'] = gridiron_ink_template

# 5. Set it as the default theme for all future charts
pio.templates.default = 'gridiron_ink'

# ── Chart style constants ────────────────────────────────────────────────────
# Change a value here to update every chart that references it at once.

LABEL_COLOR  = '#FFC300'   # gold — accent annotations (VS. labels, corner labels, column headers)
TEXT_COLOR   = '#BDE2FF'   # blue-white — facet/subplot titles, general annotation text

LEGEND_STD = dict(         # standard horizontal-top layout for all charts with a visible legend
    orientation='h', x=0.5, xanchor='center',
    y=1.02, yanchor='bottom', font=dict(size=14), title=''
)

MARGIN_STD      = dict(t=130, b=100, l=80,  r=40)   # default single chart
MARGIN_HBAR_MED = dict(t=130, b=100, l=180, r=40)   # horizontal bar, medium-length labels
MARGIN_HBAR     = dict(t=130, b=100, l=200, r=40)   # horizontal bar, long labels
# ─────────────────────────────────────────────────────────────────────────────

# ── Roster IDs ───────────────────────────────────────────────────────────────
roster_ids_2019 = {1: 'bgmaddox', 2: 'jlglover', 3: 'akbrown29', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'YouthPastor', 8: 'BillyRayGonnaGetcha',
 9: 'GurlyGirls', 10: 'SweetDizzzzzle', 11: 'RossLikeSauce', 12: 'JTizzzzle'}
roster_ids_2020 = {1: 'bgmaddox', 2: 'jlglover', 3: 'JTizzzzle', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'YouthPastor', 8: 'jhuntmadd',
 9: 'RReclam', 10: 'SweetDizzzzzle'}
roster_ids_2021 = {1: 'bgmaddox', 2: 'jlglover', 3: 'JTizzzzle', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'YouthPastor', 8: 'jhuntmadd',
 9: 'RReclam', 10: 'SweetDizzzzzle', 11: 'RossLikeSauce', 12: 'BillyRayGonnaGetcha'}
roster_ids_2022 = {1: 'bgmaddox', 2: 'jlglover', 3: 'JTizzzzle', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'DirtyCommie', 8: 'jhuntmadd',
 9: 'RReclam', 10: 'sgmaddox', 11: 'RossLikeSauce', 12: 'Just_Here_For_The_Snacks'}
roster_ids_2023 = {1: 'bgmaddox', 2: 'jlglover', 3: 'JTizzzzle', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'DirtyCommie', 8: 'jhuntmadd',
 9: 'RReclam', 10: 'sgmaddox', 11: 'RossLikeSauce', 12: 'InfiniteJesse'}
roster_ids_2024 = roster_ids_2023
roster_ids_2025 = {1: 'bgmaddox', 2: 'jlglover', 3: 'JTizzzzle', 4: 'RascalHazard',
 5: 'BMoreBallers88', 6: 'eegrady', 7: 'DirtyCommie', 8: 'jhuntmadd',
 9: 'cosmodromedary', 10: 'sgmaddox', 11: 'RossLikeSauce', 12: 'InfiniteJesse'}

roster_ids = {2019: roster_ids_2019, 2020: roster_ids_2020, 2021: roster_ids_2021,
              2022: roster_ids_2022, 2023: roster_ids_2023, 2024: roster_ids_2024,
              2025: roster_ids_2025}


def get_slot_teamcolors(year, colorway=None):
    """Return {team_name: color} keyed by roster slot order for a given year.

    Colors follow the slot number (1-indexed), not alphabetical order.
    When a player takes over a slot, they inherit that slot's color.
    """
    if colorway is None:
        colorway = coastal_colorway
    slots = roster_ids.get(year, {})
    return {name: colorway[(slot - 1) % len(colorway)]
            for slot, name in sorted(slots.items())}


def get_alltime_teamcolors(colorway=None):
    """Return {team_name: color} for every player across all years.

    Colors are assigned by join order (first appearance across all years/slots),
    so each player gets a permanently unique color regardless of which slot they occupy.
    The first 12 entries of alltime_colorway match coastal_colorway, so 2019 charter
    members' all-time colors align with their per-year slot colors.
    """
    if colorway is None:
        colorway = alltime_colorway
    seen = {}
    for year in sorted(roster_ids.keys()):
        for slot, name in sorted(roster_ids[year].items()):
            if name not in seen:
                seen[name] = colorway[len(seen) % len(colorway)]
    return seen


positions = {0: 'QB', 1: 'RB1', 2: 'RB2', 3: 'WR1', 4: 'WR2', 5: 'TE', 6: 'WRT', 7: 'K', 8: 'DEF'}
position_list = list(positions.values())

# ── League IDs ───────────────────────────────────────────────────────────────
leagueID_2019 = 464552024260734976
leagueID_2020 = 601250643570659328
leagueID_2021 = 726148502706589696
leagueID_2022 = 861038938700255232
leagueID_2023 = 992181788975620096
leagueID_2024 = 1122303756063965184
leagueID_2025 = 1252049821154410496
Survivor_leagueID_2024 = 1136802217681539072

leagueNumbers_Dict = {
    2019: leagueID_2019, 2020: leagueID_2020, 2021: leagueID_2021,
    2022: leagueID_2022, 2023: leagueID_2023, 2024: leagueID_2024, 2025: leagueID_2025,
}

AVAILABLE_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

# ── Global Match Dicts (populated as Week objects are created) ───────────────
Matches_2019 = {}; Matches_2020 = {}; Matches_2021 = {}; Matches_2022 = {}
Matches_2023 = {}; Matches_2024 = {}; Matches_2025 = {}
Breakout_Matches_2019 = {}; Breakout_Matches_2020 = {}; Breakout_Matches_2021 = {}
Breakout_Matches_2022 = {}; Breakout_Matches_2023 = {}; Breakout_Matches_2024 = {}
Breakout_Matches_2025 = {}

AllMatchesDict = {
    2019: Matches_2019, 2020: Matches_2020, 2021: Matches_2021, 2022: Matches_2022,
    2023: Matches_2023, 2024: Matches_2024, 2025: Matches_2025,
}
AllBreakoutDict = {
    2019: Breakout_Matches_2019, 2020: Breakout_Matches_2020, 2021: Breakout_Matches_2021,
    2022: Breakout_Matches_2022, 2023: Breakout_Matches_2023, 2024: Breakout_Matches_2024,
    2025: Breakout_Matches_2025,
}

OptimalScores2019 = {}; OptimalScores2020 = {}; OptimalScores2021 = {}
OptimalScores2022 = {}; OptimalScores2023 = {}; OptimalScores2024 = {}; OptimalScores2025 = {}
OptimalScoresByYear = {
    2019: OptimalScores2019, 2020: OptimalScores2020, 2021: OptimalScores2021,
    2022: OptimalScores2022, 2023: OptimalScores2023, 2024: OptimalScores2024,
    2025: OptimalScores2025,
}

AllSeasonsBreakoutList = [Breakout_Matches_2019, Breakout_Matches_2020, Breakout_Matches_2021,
                           Breakout_Matches_2022, Breakout_Matches_2023, Breakout_Matches_2024,
                           Breakout_Matches_2025]
AllMatchesList = [Matches_2019, Matches_2020, Matches_2021, Matches_2022,
                  Matches_2023, Matches_2024, Matches_2025]


class League:
    def __init__(self,year, id):
        self.year = year
        self.id = id
        self.SettingsJSONtoDF()
        
        self.UsersJSONtoDF()
        self.UserSetup()
        
        self.schedule = nfl.import_schedules([year])
        self.ScheduleFormater()
        self.StructureWeekIDs()
        # Use nflverse-data direct CSVs for all years — consistent schema (team col, not recent_team),
        # works for any future year without code changes.
        self.WeeklyNFLData = pd.read_csv(
            f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{year}.csv',
            low_memory=False
        )
        self.StructureNFLData()
        self.Rosters = nfl.import_rosters([year])
        self.PlayerTeamImport()
        self.Player_Pos_Dict()
        

        print(f'League for {self.year} created.')

    def SettingsJSONtoDF(self):
        league_settings_request = requests.get(f'https://api.sleeper.app/v1/league/{self.id}')
        league_settings_json = league_settings_request.json()
        league_settings_json_normal = json_normalize(league_settings_json)
        self.league_settings = league_settings_json_normal.T.set_axis(['league_setting'], axis=1).to_dict()['league_setting']
    
    def UsersJSONtoDF(self):
        league_user_response = requests.get(f'https://api.sleeper.app/v1/league/{self.id}/users')
        league_user_json = league_user_response.json()

        self.Members = json_normalize(league_user_json)
        self.OwnerIDDict = dict(zip(self.Members.user_id , self.Members.display_name))

    def StructureWeekIDs(self):
        self.schedule['teams'] = self.schedule[['home_team','away_team']].values.tolist()
        self.schedule = self.schedule.explode('teams')
        self.schedule['week_id'] = self.schedule['teams'] + '-' + self.schedule['week'].astype(str)

    def StructureNFLData(self):
        # nflverse CSVs use 'team'; normalize to 'recent_team' for all downstream code
        self.WeeklyNFLData = self.WeeklyNFLData.copy()
        self.WeeklyNFLData['recent_team'] = self.WeeklyNFLData['team']
        self.WeeklyNFLData['week_id'] = self.WeeklyNFLData['recent_team'] + '-' + self.WeeklyNFLData['week'].astype(str)
        
    

    def PlayerTeamImport(self):
        # 'recent_team' already normalized in StructureNFLData
        self.player_team_DF_Import = self.WeeklyNFLData[['player_display_name', 'recent_team']].drop_duplicates()
        self.player_team_DF = self.Rosters[['player_name', 'team']].drop_duplicates()

    
        
    
    def Player_Pos_Dict(self):
        player_df = pd.DataFrame.from_dict(NFLPlayerData, orient='index').reset_index()
        player_df = player_df.rename(columns={'index':'index_id'})
        
        player_mask = player_df['index_id'].astype(str).str.contains('[A-Z]')
        player_df.loc[player_mask,'full_name'] = player_df['index_id']
        player_names = player_df.set_index('player_id').to_dict()['full_name']
        player_pos = player_df.set_index('player_id').to_dict()['position']
        player_names['0'] = "Missing"
        player_names['OAK'] = 'OAK'
        player_pos['0'] = 'Missing'
        
        self.player_df = player_df
        self.player_names = player_names
        self.player_pos = player_pos
    
    def UserSetup(self):
        self.Members = self.Members.reset_index().rename({'index':'player_code'},axis=1)
        self.Members['player_code'] = self.Members['player_code'] + 1
        self.Teams = dict(zip(self.Members.player_code,self.Members.display_name))

    def ImportWeek(self, week):
        week_response = requests.get(f'https://api.sleeper.app/v1/league/{self.id}/matchups/{week}')
        week_json = week_response.json()
        return week_json
    
    def ScheduleFormater(self):
        self.schedule['gametime_gameday'] = self.schedule['gameday'] + ' ' + self.schedule['gametime']
        self.schedule['gametime_gameday'] = self.schedule['gametime_gameday'].apply(lambda x: pd.Period(x, freq='ms'))
        self.schedule['gametime_gameday'] = self.schedule['gametime_gameday'].astype(str)
        
        self.schedule['gametime_gameday'] = pd.to_datetime(self.schedule['gametime_gameday'], format='mixed')
        self.schedule['gametime_gameday_sorting'] = self.schedule['gametime_gameday']

        self.schedule['gametime_format']= self.schedule['gametime'].apply(lambda x: pd.Period(x, freq='ms')).dt.strftime('%I %p')
        self.schedule['weekday_str'] = pd.to_datetime(self.schedule['gameday']).dt.strftime('%a')
        #self.schedule['weekday_str'] = self.schedule['gameday'].dt.strftime('%a')
        self.schedule['gametime_str'] = self.schedule['gametime_format'].astype(str).replace("^0", "", regex=True)
        self.schedule['Tick']= "<b>" + self.schedule['weekday_str']  + '</b><br><sup>' + self.schedule['gametime_str'] + '</sup>'
        self.schedule['gametime_gameday_format'] = self.schedule['gametime_gameday'].dt.strftime('%A %I %p')
        #self.schedule['gametime_gameday_format'] = pd.to_datetime(self.schedule['gametime_gameday_format']).dt.strftime('%A %I %p')
        
        self.schedule = self.schedule.sort_values('gametime_gameday')
        self.ScheduleGroup = self.schedule.groupby('week')

        
    
    def Draft(self):
        draft_id = self.league_settings['draft_id']
        draft_request = requests.get(f'https://api.sleeper.app/v1/draft/{draft_id}/picks')
        draft_json = draft_request.json()
        draft_json_normal = json_normalize(draft_json)
        draft_json_normal.roster_id = draft_json_normal['roster_id'].map(self.Teams)
        draft_json_normal['player_name'] = draft_json_normal['player_id'].map(self.player_names)
        draft_json_normal['year'] = self.year
        self.draft = draft_json_normal
        return self.draft
    
class Week:
    def __init__(self,week, league):
        self.week = week
        self.league = league
        self.id = self.league.id
        self.year = self.league.year
        
        self.ImportWeek()
        self.WeeklyDataframe()
        self.SetTeamColors()
        self.PlayerBreakout()
        if self.year != CURRENT_SEASON:
            self.OptimalTeams()

            self.EfficincyScore()

        
    
    def Update(self):
        self.ImportWeek()
        self.PlayerBreakout()
        self.WeeklyDataframe()
            
    
    def ImportWeek(self):
        week_response = requests.get(f'https://api.sleeper.app/v1/league/{self.id}/matchups/{self.week}')
        week_json = week_response.json()
        self.json = week_json

    def SetTeamColors(self, color_dict:dict = None):
        self.teamcolors = get_slot_teamcolors(self.year)
        if color_dict is not None:
            self.teamcolors = color_dict
    
    def UpdateColors(self ,fig):
        """
        Updates the y-axis tick labels of a figure to use team-specific colors.
        """
        # --- THE FIX ---
        # Instead of 'categoryarray', we get labels directly from the figure's data trace.
        # This is a more reliable way to access the list of teams on the y-axis.
        if not fig.data or fig.data[0].y is None:
            # Failsafe in case the figure has no data
            return fig

        y_axis_labels = fig.data[0].y
        
        # Create a new list of HTML-styled labels with the correct colors.
        styled_labels = []
        for label in y_axis_labels:
            # Look up the color for the team from your dictionary
            color = self.teamcolors.get(label, 'white') # Default to white if not found
            styled_labels.append(f"<span style='color:{color}'>{label}</span>")

        # Update the y-axis to use the new styled text.
        # 'tickvals' provides the original labels to map against.
        # 'ticktext' provides the new, styled labels to display.
        fig.update_yaxes(
            tickvals=y_axis_labels,
            ticktext=styled_labels
        )
                
        return fig
    
    def PlayerBreakout(self):
        # Initialize an empty list to hold the rows
        JSON_data = self.json
        player_data = self.league.player_team_DF
        rows = []
        
        Regular = list(range(1,15))
        Playoff = list(range(15,19))

        WeeklyNFLData = self.league.WeeklyNFLData
        schedule = self.league.schedule
        NFLTeamList =self.league.player_team_DF_Import['recent_team'].unique()

        Defence = pd.DataFrame(NFLTeamList)
        Defence = Defence.rename(columns={0:'player_name'})
        Defence['team'] = NFLTeamList
        
        player_team_DF = pd.concat([player_data,Defence])
        
        player_team_DF['player_name'] = player_team_DF['player_name'].replace(' Jr.','', regex=True).replace(' Sr.','', regex=True).replace(' III','',regex=True).replace(' II','',regex=True)

        
        #Player Corrections
        player_team_DF = player_team_DF.drop(1035)
        player_team_DF = player_team_DF.replace('Marquise Brown','Hollywood Brown')
        player_team_DF = player_team_DF.replace('Audric Estimé','Audric Estime')

        # player_team_DF = player_team_DF.replace('Zonovan Knight','Bam Knight')
        player_team_DF.loc[-1] = ['LAR','LA']

        
        player_team_DF.index = player_team_DF.index+1
        player_team_DF = player_team_DF.sort_index()
        
        for team in JSON_data:
            # Extract relevant information
            matchup_id = team['matchup_id']
            roster_id = team['roster_id']
            players_points = team['players_points']
            starters = team['starters']

            # Iterate through each player and their points
            for player, points in players_points.items():
                # Determine if the player is a starter
                is_starter = player in starters
                
                player_name = self.league.player_names.get(player, player)  # Default to player ID if name not found
                player_positions = self.league.player_pos.get(player, 0)

                # Create a row for each player
                rows.append({
                    'team': roster_id,
                    'matchup': matchup_id,
                    'player_id': player,
                    'player': player_name,
                    'points': points,
                    'starter': int(is_starter),
                    'position': player_positions
                })
        
        # Convert the list of rows into a DataFrame
        dfBreakout = pd.DataFrame(rows)
        league_names = roster_ids[self.year]
        dfBreakout['team'] = dfBreakout['team'].replace(league_names)
        dfBreakout['week'] = self.week
        dfBreakout['year'] = self.year
        
        player_team_DF['player_name'] = player_team_DF['player_name'].replace(' Jr.',' Jr', regex=True).replace(' Sr.',' Sr', regex=True).replace(' III','',regex=True).replace(' II','',regex=True)

        dfBreakout = dfBreakout.merge(player_team_DF, left_on='player', right_on='player_name', how = 'left')
        dfBreakout['player_name'] = dfBreakout['player_name'].replace(' Jr.',' Jr', regex=True).replace(' Sr.',' Sr', regex=True).replace(' III','',regex=True).replace(' II','',regex=True)

        dfBreakout['week_id'] = dfBreakout['team_y'] + '-' + dfBreakout['week'].astype(str)
        
        if self.week in Regular:
            dfBreakout['Season'] = 'Regular'
        elif self.week in Playoff:
            dfBreakout['Season'] = 'Playoff'

        dfBreakout['player_week_id'] = dfBreakout['player'] + ' - ' + dfBreakout['week'].astype(str)
        WeeklyNFLData['player_display_name'] = WeeklyNFLData['player_display_name'].replace(' Jr.','', regex=True).replace(' Sr.','', regex=True) \
                                                .replace(' III','',regex=True).replace('Bam Knight','Zonovan Knight', regex=True).replace(' II','',regex=True)
        WeeklyNFLData['player_week_id'] = WeeklyNFLData['player_display_name'] + ' - ' + WeeklyNFLData['week'].astype(str)
        
        
        dfBreakout = dfBreakout.merge(schedule, on = 'week_id', how = 'left')
        # suffixes=('','_roster') preserves 'position' as the Sleeper fantasy position (QB/RB/WR/TE/K/DEF)
        dfBreakout = dfBreakout.merge(self.league.Rosters, on='player_name', how='left', suffixes=('', '_roster'))

        dfBreakout = dfBreakout.merge(WeeklyNFLData, on = 'player_week_id', how = 'left', suffixes=('','_NFL'))
        # Drop rows duplicated by name collisions in nflverse (e.g., two NFL players sharing a display name)
        dfBreakout = dfBreakout.drop_duplicates(subset=['team_x', 'player', 'week'])
        dfBreakout['gametime'] = pd.to_datetime(dfBreakout['gametime'], format='mixed').dt.strftime('%I %p')
        dfBreakout['Game_date_time'] = dfBreakout['weekday'] + ' ' + dfBreakout['gametime'].astype(str).replace(r'0', "", regex=True)
        dfBreakout = dfBreakout.rename(columns={'team_x':'team','team_y':'recent_teams'})
        dfBreakout = dfBreakout.loc[:,~dfBreakout.columns.duplicated()].copy()
        if self.year != CURRENT_SEASON: dfBreakout['color'] = dfBreakout['team'].map(self.teamcolors)
        
        self.Breakout = dfBreakout
        Breakout_Year_Dict = AllBreakoutDict[self.year]
        Breakout_Year_Dict[self.week] = dfBreakout
        
    
    def WeeklyDataframe(self):
        # Create an empty dictionary to hold the DataFrame data
        df_dict = {}
        matchup_dict = {}

        # Iterate through each team and their data
        for team in self.json:
            roster_id = team["roster_id"]
            starters = team['starters']
            starters_points = team['starters_points']
            matchup_id = team['matchup_id']
            
            # Replace player IDs with player names
            starters_with_names = [self.league.player_names.get(player, f"Unknown ({player})") for player in starters]
            
            # Combine players and their points into a list where each entry is a list [dictionary, matchup_id]
            df_dict[roster_id] = [{player: points} for player, points in zip(starters_with_names, starters_points)]
            matchup_dict[roster_id] = matchup_id

        # Create a DataFrame from the dictionary
        WeeklyDf = pd.DataFrame.from_dict(df_dict, orient='index')

        WeeklyDf['Matchup'] = WeeklyDf.index.map(matchup_dict)
        # Define a function to sum the values in the dictionaries in each row
        def sum_points(row):
            total = 0
            for entry in row:
                if isinstance(entry, dict):
                    total += sum(entry.values())
            return total

        league_names = roster_ids[self.year]
        # Apply the function to each row to create the 'Total' column
        WeeklyDf['Total'] = WeeklyDf.apply(sum_points, axis=1)
        WeeklyDf = WeeklyDf.rename(index = league_names)
        
        # Step 1: Group by 'Matchup_ID' and get the maximum 'Total' for each group
        max_scores = WeeklyDf.groupby('Matchup')['Total'].transform('max')
    
    

        # Step 2: Create a new column 'Won' that checks if the team's 'Total' equals the max score
        WeeklyDf['Won'] = WeeklyDf['Total'] == max_scores

        # Step 3: Optional - Convert the boolean 'Won' column to 1 (win) and 0 (loss)
        WeeklyDf['Won'] = WeeklyDf['Won'].astype(int)
        
        
        WeeklyDf['Opp'] = np.where(WeeklyDf['Won'] == 1,WeeklyDf.groupby('Matchup')['Total'].transform('min'),WeeklyDf.groupby('Matchup')['Total'].transform('max'))
        
        WeeklyDf['Margin'] = WeeklyDf['Total'] - WeeklyDf['Opp']
        #WeeklyDf.loc[[WeeklyDf['Won']] == 1,'Opp Score'] = WeeklyDf.groupby('Matchup')['Total'].transform('max')
        #WeeklyDf.loc[[WeeklyDf['Won']] == 0,'Opp Score'] = WeeklyDf.groupby('Matchup')['Total'].transform('min')
        
        
        WeeklyDf = WeeklyDf.rename(columns=positions).sort_values('Matchup')
        WeeklyDf = WeeklyDf.reset_index().rename({'index':'Team'}, axis = 1)
        WeeklyDf['Week'] = self.week
        WeeklyDf['Season'] = "Regular" if self.week < 15 else "Playoff"
        WeeklyDf['Week Index'] = self.week + (14 * (self.year - 2019))
        WeeklyDf['Year'] = self.year
        
        percent = WeeklyDf.groupby('Week')['Total'].sum()
        percent = percent.reset_index()
        WeekTotal = dict(zip(percent['Week'],percent['Total']))
        
        WeeklyDf['LeagueTotal'] = WeeklyDf['Week'].map(WeekTotal)
        WeeklyDf['PercentTotal'] = ((WeeklyDf['Total'] / WeeklyDf['LeagueTotal']) * 100).round(1)
        # Use groupby to assign the opposing team's name
        #WeeklyDf['Opp_team'] = WeeklyDf.groupby('Matchup')['Team'].transform(lambda x: x.shift(-1) if x.index[0] % 2 == 0 else x.shift(1))
        # Define a function to get the opponent team name for each group
        def get_opponent(teams):
            return teams[::-1]  # Reverse the order so each team gets the other team as opponent

        # Apply the function group-wise to assign opposing teams
        #WeeklyDf['Opp_team'] = WeeklyDf.groupby('Matchup')['Team'].transform(get_opponent)
        # Define a function to assign the opponent team name
        def assign_opponents(group):
            # Assuming there are exactly two teams per matchup
            teams = group['Team'].values
            if len(teams) == 2:  # For valid matchups with two teams
                group['Opp_team'] = [teams[1], teams[0]]  # Swap the teams
            return group

        # Apply the function to each matchup
        # Note: pandas 3.x drops the groupby column from apply() results,
        # so we assign opponents without losing 'Matchup'.
        opp_map = {}
        for _, grp in WeeklyDf.groupby('Matchup'):
            teams = grp['Team'].values
            if len(teams) == 2:
                opp_map[teams[0]] = teams[1]
                opp_map[teams[1]] = teams[0]
        WeeklyDf['Opp_team'] = WeeklyDf['Team'].map(opp_map)
            
        WeeklyDfMatches= WeeklyDf.set_index(['Matchup','Team'])
        WeeklyDfNoMatches = WeeklyDf.set_index('Team')
        WeeklyDfClean = WeeklyDf.set_index('Team').drop(columns=['Total','Won','Week','Opp','Margin'])
        
        self.WeeklyMatches = WeeklyDfMatches
        self.WeeklyNoMatches = WeeklyDfNoMatches
        self.WeeklyClean = WeeklyDfClean

        Dict_to_Add = AllMatchesDict[self.year]
        Dict_to_Add[self.week] = self.WeeklyNoMatches.reset_index()
        
        
    def OptimalTeams(self):    
        OptimalDF = self.Breakout

        position_counts = {
            'QB': 1,
            'RB': 2,
            'WR': 2,
            'TE': 1,
            'DEF': 1,
            'K': 1
        }
        # Define which positions are eligible for the FLEX spot
        flex_eligible_positions = ['RB', 'WR', 'TE']

        OptGroups = OptimalDF.groupby(['team', 'position'])
        DreamGroups = OptimalDF.groupby('position')
        core_lineup_df = pd.DataFrame()
        dream_lineup_df = pd.DataFrame()

        for name, group in OptGroups:
            position = name[1]
            # Use .get() to safely handle positions not in your dictionary (e.g., FLEX)
            # It will default to 0 if the position isn't found.
            num_players = position_counts.get(position, 0)

            if num_players > 0:
                topPlayers = group.sort_values('points', ascending=False).head(num_players)
                core_lineup_df = pd.concat([core_lineup_df, topPlayers])

        for position, group in DreamGroups:
            position = name[1]
            
            num_players = position_counts.get(position, 0)

            if num_players > 0:
                dreamPlayers = group.sort_values('points', ascending=False).head(num_players)
                dream_lineup_df = pd.concat([dream_lineup_df, dreamPlayers])

        # Create a pool of players who are NOT in the core lineup
        flex_pool_df = OptimalDF.drop(core_lineup_df.index)
        flex_dream_pool_df = OptimalDF.drop(dream_lineup_df.index)

        # Filter this pool to only include FLEX-eligible positions
        flex_pool_df = flex_pool_df[flex_pool_df['position'].isin(flex_eligible_positions)]
        flex_dream_pool_df = flex_dream_pool_df[flex_dream_pool_df['position'].isin(flex_eligible_positions)]

        # For each team, find the single highest-scoring player in the flex_pool_df
        # The .loc[...idxmax()] pattern is a very efficient way to do this
        flex_players_df = flex_pool_df.loc[flex_pool_df.groupby('recent_team')['points'].idxmax()]
        flex_dream_pool_df = flex_dream_pool_df.loc[flex_dream_pool_df['points'].idxmax()]

        # For clarity, let's add a column to show where each player started
        core_lineup_df['starting_position'] = core_lineup_df['position']
        flex_players_df['starting_position'] = 'FLEX'
        dream_lineup_df['starting_position'] = dream_lineup_df['position']
        flex_dream_pool_df['starting_position'] = 'FLEX'

        # Concatenate the two DataFrames to get the final, complete optimal lineup
        final_optimal_lineup = pd.concat([core_lineup_df, flex_players_df])
        if self.year != CURRENT_SEASON:
            final_dream_team = pd.concat([dream_lineup_df, flex_dream_pool_df])
            self.DreamTeamDF = final_dream_team

        # Sort for a clean final view
        final_optimal_lineup = final_optimal_lineup.sort_values(
            by=['recent_team', 'starting_position'], 
            ascending=True
        )

        self.OptimalScoresDict = dict(final_optimal_lineup.groupby('team')['points'].sum().round(2))
        self.OptimalScoresDF = final_optimal_lineup
        


    def EfficincyScore(self):
        self.OptimalTeams()
        self.Scores = self.WeeklyNoMatches.to_dict()['Total']
        eff_score = {}
        for team , score in self.Scores.items():
            eff_score[team] = ((score / self.OptimalScoresDict[team]) * 100).round(1)
        
        self.efficiency = eff_score
        Dict_to_Add_To = OptimalScoresByYear[self.year]
        Dict_to_Add_To[self.week] = self.OptimalScoresDF
        
    def LuckScore(self):
        SeasonObject = Season_Dict[self.year]
        WeekRange = [1,self.week+1]
        Season = SeasonObject.Matches
        Season = Season[Season['Week'].isin(WeekRange)]
        self.AverageScores = Season.groupby('Team')['Total'].mean().round(1).rename('Averages')   

        Averages = self.AverageScores
        Scores = self.WeeklyNoMatches['Total'].round(1)
        Combo = pd.concat([Averages, Scores], axis = 1)
        Combo['Luck'] = (Combo['Total'] - Combo['Averages']).round(1)
        self.LuckScores = Combo
        

    #
    # GRAPHS
    #

    def WeeklyGraph(self):
    
        #points = MatchDF.drop(columns=['Total','Won','Week','Opp','Margin']).map(lambda if isinstance(x,dict): float(list(x.values())[0]))
        points = self.WeeklyMatches.map(lambda x: float(list(x.values())[0]) if isinstance(x, dict) else x)
        points = points.round(2).reset_index()
        
        fig1 = px.bar(points, y='Team',x=position_list,template = 'gridiron_ink',color = "Matchup", barmode='group',text_auto=True, 
                      title = f'<b>Week {self.week} Matchups</b><br><sup>QB → DEF</sup>', orientation='h',
                      color_continuous_scale=px.colors.diverging.Portland)
        
        #Update the layout to hide the legend:
        fig1.update(layout_coloraxis_showscale=False)
        
        # Adjust the figure size
        fig1.update_layout(width=800, height=1200)
        
        fig1.update_traces(textfont_size=12, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(weight='bold',  # Font family
                size=12   # Font color
            ))
        
        # Customize the x-axis labels
        fig1.update_xaxes(
            tickfont=dict(
                size=16,         # Font size
            ),
            title = None
        )

        # Customize the y-axis labels
        fig1.update_yaxes(
            tickfont=dict(
                size=18, weight = 'bold'         # Font size
            ),
            title=None
        )

        # NOTE: VS. y-positions below are hardcoded for exactly 6 matchups (12 teams).
        # If the league size changes, these values need to be recalculated dynamically.
        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.93, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        ))

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.76, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.58, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.41, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.23, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.025, y=.065, xanchor='center',
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR,
            weight ='bold'
        )
        )

        
        fig1.update_traces(marker_line_width=2, marker_line_color='rgba(0,0,0,0.25)')

        fig1.update_traces(insidetextanchor= 'middle')
        fig1.update_layout(
            uniformtext_minsize=12,
            uniformtext_mode='hide'
            )

        fig1.update_traces(
            hovertemplate="<b>%{y}</b><br>%{fullData.name}: <b>%{x:.2f} pts</b><extra></extra>"
        )
        fig1.update_layout(transition=dict(duration=500, easing='cubic-in-out'))
        fig1.update_layout(margin=dict(t=120, b=90, l=170, r=40))

        apply_logo_to_fig(fig1,xval=.4,yval = -0.04)
        self.UpdateColors(fig1)

        return fig1
        
   
    
    def PointsOverTheWeekend(self, Alternate=None, animate=False):
        breakoutDF = self.Breakout
        week_num = self.week

        title_string = f'<b>Points Timeline</b><br><sup>Week {week_num}</sup>'

        TimeAreaDF = breakoutDF[breakoutDF['starter'] == 1]

        
        TimeAreaDF = TimeAreaDF.sort_values('gametime_gameday')

        TimeAreaDFGraph = TimeAreaDF.groupby(['matchup','team','gametime_gameday_format'],
                                             sort='gametime_gameday').agg({'points':'sum','gametime_gameday':'first','Game_date_time':'first' ,'Tick':'first'}).reset_index()
        

        TimeAreaDFGraph['ScoreTally'] = TimeAreaDFGraph.sort_values('gametime_gameday',ascending=True).groupby(['team']).points.cumsum()
        TimeAreaDFGraph = TimeAreaDFGraph.sort_values('gametime_gameday')

        TeamNames = TimeAreaDFGraph.groupby('matchup').team.unique().reset_index()
        TeamNames['MatchupTitle'] = TeamNames.team.str.join(' vs ')
        MatchupNames = dict(zip(TeamNames.matchup, TeamNames.MatchupTitle))
        TimeAreaDFGraph['MatchupTitle'] = TimeAreaDFGraph.matchup.map(MatchupNames)
        ## NEED TO FIGURE OUT THE SORTING OF THE GAMES BEFORE THE CUMULATION IS DONE

        GameList = self.league.ScheduleGroup.get_group(self.week)['gametime_gameday_format'].unique().tolist()
        TickList = self.league.ScheduleGroup.get_group(self.week)['Tick'].unique().tolist()
        self.GametimeList = TimeAreaDFGraph['gametime_gameday_format'].unique()
       
        self.TickList = TickList
        GametimeList = self.GametimeList
        GameListLen = len(GameList)
            
        TimeAreaDFGraph['color'] = TimeAreaDFGraph['team'].map(self.teamcolors) 

        figWeekLine = px.area(TimeAreaDFGraph.sort_values(['matchup','gametime_gameday']), x='gametime_gameday_format', y = 'ScoreTally',color = 'team',color_discrete_map=self.teamcolors, 
                              template = 'gridiron_ink', 
                            facet_col='MatchupTitle', facet_col_wrap=2,  facet_col_spacing=0.10,  facet_row_spacing=0.10, title=title_string, markers=True)
        figWeekLine.update_layout(height=1200, width = 1000)
       
        figWeekLine.update_traces(stackgroup=None,fill='tozeroy', line_shape = 'spline')
        figWeekLine.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        figWeekLine.update_layout(showlegend=False)
        figWeekLine.update_xaxes(title_text="", side = 'bottom',tickfont=dict(size=20),
                                 ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format'])
        
        # Update facet titles to include team colors
        for annotation in figWeekLine.layout.annotations:
            title_text = annotation.text  # e.g., "Team A vs Team B"
            teams = title_text.split(" vs ")  # Split into individual team names
            # Create a styled title with team names in respective colors
            annotation.text = f"<span style='color:{self.teamcolors[teams[0]]}'>{teams[0]}</span> vs " \
                            f"<span style='color:{self.teamcolors[teams[1]]}'>{teams[1]}</span>"
            annotation.font.size = 23  # Optional: Adjust font size for clarity

        
        # hide subplot y-axis titles and x-axis titles
        for axis in figWeekLine.layout:
            if type(figWeekLine.layout[axis]) == go.layout.YAxis:
                figWeekLine.layout[axis].title.text = ''
            if type(figWeekLine.layout[axis]) == go.layout.XAxis:
                figWeekLine.layout[axis].title.text = ''
        figWeekLine.update_yaxes( showticklabels=True, visible=True)
        figWeekLine.update_xaxes( showticklabels=True, visible=True,ticktext=TickList)
        TimeAreaDFGraph = TimeAreaDFGraph.sort_values('gametime_gameday')

        figWeekLine.update_layout(
            xaxis=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis1=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis2=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis3=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis4=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis5=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            xaxis6=dict(ticktext=TimeAreaDFGraph['Tick'], tickvals = TimeAreaDFGraph['gametime_gameday_format']),
            )
        figWeekLine.update_layout(xaxis=dict(categoryorder='array',categoryarray =self.GametimeList))

        self.TimeAreaData = TimeAreaDFGraph

        figWeekLine.update_layout(margin=dict(t=120, b=90, l=50, r=50))

        figWeekLine.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Pts: <b>%{y:.2f}</b><extra></extra>"
        )

        apply_logo_to_fig(figWeekLine,xval=0,yval = 1.06)

        if animate:
            # Sorted unique game times for progressive frame reveal
            time_order = (
                TimeAreaDFGraph[['gametime_gameday_format', 'gametime_gameday']]
                .drop_duplicates('gametime_gameday_format')
                .sort_values('gametime_gameday')['gametime_gameday_format']
                .tolist()
            )

            frames = []
            for i, t in enumerate(time_order):
                current_times = set(time_order[:i + 1])
                frame_df = TimeAreaDFGraph[TimeAreaDFGraph['gametime_gameday_format'].isin(current_times)]
                frame_traces = []
                for trace in figWeekLine.data:
                    td = frame_df[frame_df['team'] == trace.name].sort_values('gametime_gameday')
                    frame_traces.append(go.Scatter(
                        x=td['gametime_gameday_format'].tolist(),
                        y=td['ScoreTally'].tolist(),
                    ))
                frames.append(go.Frame(data=frame_traces, name=str(i)))

            figWeekLine.frames = frames
            figWeekLine.update_layout(
                updatemenus=[dict(
                    type='buttons',
                    showactive=False,
                    x=0.0, y=1.08, xanchor='left', yanchor='top',
                    buttons=[
                        dict(
                            label='▶  Play',
                            method='animate',
                            args=[None, dict(frame=dict(duration=900, redraw=True),
                                             fromcurrent=True, mode='immediate',
                                             transition=dict(duration=300, easing='cubic-in-out'))],
                        ),
                        dict(
                            label='⏸  Pause',
                            method='animate',
                            args=[[None], dict(frame=dict(duration=0, redraw=False), mode='immediate')],
                        ),
                    ],
                    font=dict(color='#163146'),
                    bgcolor='#FFC300',
                    bordercolor='#FFC300',
                )]
            )

        return figWeekLine
        
    
    
class Season:
    def __init__(self, league):
        self.league = league
        self.id = self.league.id
        self.year = self.league.year
        
        
        print(f'Season for {self.year} created.')
    
    def Update(self):
        self.AllMatchesConcat()
        self.BreakoutConcat()
        
        #self.CalculateAverages()
        self.SetTeamColors()
        print(f'Season has been udpated.')
    
    def BreakoutConcat(self, last_week = None):
        # Filter out the dataframes corresponding to months up to and including the current month
        df_dict = AllBreakoutDict[self.year]
        if last_week != None:
            Week = last_week
        else:
            Week = max(df_dict.keys()) if df_dict else 1
        dataframes_to_concat = [df_dict[week] for week in range(1, Week + 1) if week in df_dict]
        self.Breakout_dict = df_dict
        # Concatenate the selected dataframes
        Weeks= pd.concat(dataframes_to_concat, axis=0)
        
        Weeks['Score YTD'] = Weeks.groupby('player')['points'].cumsum()
        Weeks['TotalYTD'] = Weeks.groupby('player')['points'].transform('sum')
        Weeks['Year'] = self.year

        self.BreakoutSeason = Weeks
        
        self.Starters = Weeks[Weeks['starter'] == 1]

    def SetBest(self,TotalYTD):
        self.Best = self.BreakoutSeason[self.BreakoutSeason['TotalYTD'] > TotalYTD]
        print(f'Best set at {self.Best}')

    def SetTeamColors(self, color_dict:dict = None):
        self.teamcolors = get_slot_teamcolors(self.year)
        if color_dict is not None:
            self.teamcolors = color_dict
        
    def UpdateColors(self ,fig):
        """
        Updates the y-axis tick labels of a figure to use team-specific colors.
        """
        # --- THE FIX ---
        # Instead of 'categoryarray', we get labels directly from the figure's data trace.
        # This is a more reliable way to access the list of teams on the y-axis.
        if not fig.data or fig.data[0].y is None:
            # Failsafe in case the figure has no data
            return fig

        y_axis_labels = fig.data[0].y
        
        # Create a new list of HTML-styled labels with the correct colors.
        styled_labels = []
        for label in y_axis_labels:
            # Look up the color for the team from your dictionary
            color = self.teamcolors.get(label, 'white') # Default to white if not found
            styled_labels.append(f"<span style='color:{color}'>{label}</span>")

        # Update the y-axis to use the new styled text.
        # 'tickvals' provides the original labels to map against.
        # 'ticktext' provides the new, styled labels to display.
        fig.update_yaxes(
            tickvals=y_axis_labels,
            ticktext=styled_labels
        )
                
        return fig

    def AllMatchesConcat(self):
        
        MatchDictionary = AllMatchesDict[self.year]
        self.Matches = pd.concat(MatchDictionary.values())
        
    def CalculateAverages(self, WeekNum):
        df = self.Matches[self.Matches['Week'].isin(range(0,WeekNum+1))]
        self.AverageScores = df.groupby('Team')['Total'].mean().round(1).rename('Averages')   
        return self.AverageScores
        
    
    def WeeklyWins(self, last_week = None):
        Weeks = self.Matches

        if last_week != None:    
            # Filter out the dataframes corresponding to months up to and including the current month
            df_dict = AllMatchesDict[self.year]
                            
            dataframes_to_concat = [df_dict[week] for week in range(1, last_week + 1)]
        
            # Concatenate the selected dataframes
            Weeks = pd.concat(dataframes_to_concat, axis=0)
        
        Weeks['Total Wins'] = Weeks.groupby('Team')['Won'].cumsum()

        Weeks['Score YTD'] = Weeks.groupby('Team')['Total'].cumsum()

        Weeks['Opp YTD'] = Weeks.groupby('Team')['Opp'].cumsum()
        
        Week_Pivot = Weeks.pivot(index = 'Team', columns = 'Week',values = 'Total Wins')
        
        self.Week_Pivot = Week_Pivot
        self.ConcatinatedWeeks = Weeks

    def OptimalTeams(self):    
        OptimalDF = self.BreakoutSeason.groupby(['team', 'player', 'position'])['points'].sum().reset_index()
        DreamDF = self.BreakoutSeason.groupby(['team', 'position','player'])['points'].sum().reset_index()

        position_counts = {
            'QB': 1,
            'RB': 2,
            'WR': 2,
            'TE': 1,
            'DEF': 1,
            'K': 1
        }
        # Define which positions are eligible for the FLEX spot
        flex_eligible_positions = ['RB', 'WR', 'TE']
        num_flex_spots = 1

        OptGroups = OptimalDF.groupby(['team', 'position'])
        DreamGroups = OptimalDF.groupby(['position'])

        core_lineup_df = pd.DataFrame()
        dream_lineup_df = pd.DataFrame()

        final_optimal_lineup_list = []

        # Process each team individually
        for team_name, team_df in OptimalDF.groupby('team'):
            
            # --- Part A: Handle the non-FLEX positions (QB, K, DEF) ---
            non_flex_starters = pd.DataFrame()
            for pos in ['QB', 'K', 'DEF']:
                # Find the best player for the team at that position
                top_player = team_df[team_df['position'] == pos].nlargest(position_counts[pos], 'points')
                non_flex_starters = pd.concat([non_flex_starters, top_player])

            # --- Part B: Handle the combined RB/WR/TE/FLEX pool ---
            
            # Create one big pool of all FLEX-eligible players for the team
            flex_pool = team_df[team_df['position'].isin(flex_eligible_positions)]
            
            # Determine the total number of starters to take from this pool
            total_flex_group_spots = (position_counts['RB'] + 
                                    position_counts['WR'] + 
                                    position_counts['TE'] + 
                                    num_flex_spots)

            # Find the best N players from this combined pool
            top_flex_group_players = flex_pool.nlargest(total_flex_group_spots, 'points')
            
            # --- Part C: Combine and build the team's final optimal lineup ---
            team_optimal_lineup = pd.concat([non_flex_starters, top_flex_group_players])
            final_optimal_lineup_list.append(team_optimal_lineup)
        
        # Combine the optimal lineups from all teams into one DataFrame
        final_optimal_lineup = pd.concat(final_optimal_lineup_list)
        
        ####Dream Team
        dream_team_core = pd.DataFrame()
        for position, count in position_counts.items():
            positional_players = DreamDF[DreamDF['position'] == position]
            top_players = positional_players.sort_values('points', ascending=False).head(count)
            dream_team_core = pd.concat([dream_team_core, top_players])

        # Create a pool of players who are NOT in the core lineup
      
        flex_dream_pool_df = DreamDF.drop(dream_team_core.index)

        # Filter this pool to only include FLEX-eligible positions
       
        flex_dream_pool_df = flex_dream_pool_df[flex_dream_pool_df['position'].isin(flex_eligible_positions)]

        # For each team, find the single highest-scoring player in the flex_pool_df
        # The .loc[...idxmax()] pattern is a very efficient way to do this
        
        flex_dream_pool_df = flex_dream_pool_df.sort_values('points', ascending=False).head(1)

        # For clarity, let's add a column to show where each player started
        
        dream_team_core['starting_position'] = dream_team_core['position']
        flex_dream_pool_df['starting_position'] = 'FLEX'

        # Concatenate the two DataFrames to get the final, complete optimal lineup
        final_dream_team = pd.concat([dream_team_core, flex_dream_pool_df])

        # Sort for a clean final view
        final_optimal_lineup = final_optimal_lineup.sort_values(
            by=['team', 'position'], 
            ascending=True
        )

        self.OptimalScoresDict = dict(final_optimal_lineup.groupby('team')['points'].sum().round(2))
        self.OptimalScoresDF = final_optimal_lineup
        self.DreamTeamDF = final_dream_team

         
    
    def EfficincyScore(self):
        self.OptimalTeams()
        OptScoresYear = OptimalScoresByYear[self.year]
        OptScores = pd.concat(OptScoresYear.values())
        self.Scores = dict(OptScores.groupby('team')['points'].sum())
        eff_score = {}
        for team , score in self.Scores.items():
            eff_score[team] = ((score / self.OptimalScoresDict[team]) * 100).round(1)
        
        self.efficiency = eff_score
        


    def PlayerTrends(self):
        WonGraph = self.Matches.pivot(columns = 'Week',index='Team',values = 'Won')
        WonGraph = WonGraph.replace(0,'L').replace(1,'W')
        last_five_cols = WonGraph.columns[-5:]
        
        WonGraph['Trend'] = WonGraph[last_five_cols].apply(lambda row: ' '.join(row.astype(str)), axis=1)
        self.WonGraph = WonGraph.reset_index()
        self.PlayerTrend = dict(zip(WonGraph.Team, WonGraph.Trend))
        
    def ScoreTrends(self):
        ScoreTrends = round(self.Matches.groupby('Week')['Total'].agg(['min','mean','max']),2)
        self._score_trends_df = ScoreTrends
        
        figTrends = px.line(ScoreTrends.reset_index(), x='Week', y = ['min','max','mean'], template = 'gridiron_ink',line_shape = 'spline', title = 'Scoring Trends', markers=True )
        figTrends.update_layout(
            yaxis=dict(
                range=[0, 180]  # Set the y-axis range from 0 to 10
            )
        )
        figTrends.update_layout(width=None, height=800)
        figTrends.update_layout(font_family="Courier New", title_font = dict(size=45))
        figTrends.update_yaxes(
                tickfont=dict(
                    family='Courier New',
                    size=15,
                ),
                title = None,

            )
        figTrends.update_xaxes(
                tickfont=dict(
                    family='Courier New',
                    size=15,
                ),
                title = 'Week',

            )
        figTrends.update_layout(legend=LEGEND_STD)
        figTrends.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Week %{x}<br>Score: <b>%{y:.1f}</b><extra></extra>"
        )
        figTrends.update_layout(transition=dict(duration=400, easing='cubic-in-out'))
        return figTrends
    
    def PowerRankings(self, week):
        df = self.Matches
        PlayerNum = 12

        df['Week Rank'] = df.groupby('Week')['Total'].rank().astype(int) - 1
        df = df[df['Week'] <= week]
        df['Power YTD'] = df.groupby('Team')['Week Rank'].cumsum().astype(int)
        df['Power Loss YTD'] = (df['Week'] * (PlayerNum-1) - df['Power YTD']).astype(int)
        #df['Win Percentage'] = (df['Power YTD']/(df['Week'] * week))
        df['Win Percentage'] = (df['Power YTD']/(df['Power YTD'] + df['Power Loss YTD']))
        df['Power Ranking'] = df.groupby('Week')['Win Percentage'].rank(ascending=False).astype(int)
        self.PowerRanks = df[df["Week"]== week]
        self.PowerRankDict = dict(zip(self.PowerRanks['Team'],self.PowerRanks['Power Ranking']))
        self.PowerPercentDict = dict(zip(self.PowerRanks['Team'],self.PowerRanks['Win Percentage']))


        return self.PowerRanks
        
        
    def Calc(self, WeekObj, team = None):
        self.PowerRankings(WeekObj.week)
        week = WeekObj.week
        WeeklyMatchYTD = self.Matches[self.Matches['Week'] <= week]
        

        Scores = dict(self.Matches[self.Matches['Week']== week].set_index('Team').Total.round(1))
        
        AverageScores = dict(self.CalculateAverages(week))

        LeagueAverage = WeeklyMatchYTD.Total.mean().round(1)

        ThisWeek = self.PowerRankings(week)
        PowerPercentDict = dict(zip(ThisWeek['Team'],ThisWeek['Win Percentage']))
        PowerRanks = dict(zip(ThisWeek['Team'],ThisWeek['Power Ranking']))

        

        if week != 1:
            LastWeek = self.PowerRankings(week - 1)
            
            PreviousRanks = dict(zip(LastWeek['Team'],LastWeek['Power Ranking']))
        else:
            PreviousRanks = self.PowerRankDict

        

        WeekObj.OptimalTeams()
        OptimalScores = WeekObj.OptimalScoresDict
        
        if team != None:
            team_score = Scores[team]
            team_average = AverageScores[team]
            Power = PowerPercents[team]
            CurrentRank = PowerRanks[team]
            PreviousRank = PreviousRanks[team]


        self.StatusDict = {'Scores':Scores, 'AverageScores':AverageScores, 'LeagueAverage' : LeagueAverage, 'PowerRanks': PowerRanks, 'PreviousRanks': PreviousRanks,
                      'PowerPercents':PowerPercentDict, 'OptimalScores': OptimalScores} 
          
    
    def SnakeGraph(self, week):
        self.WeeklyWins(week)
        df = self.ConcatinatedWeeks
        unique_teams = df['Team'].unique()
        week_zero_df = pd.DataFrame({
            'Team': unique_teams,
            'Week': 0,
            'Total Wins': 0
        })
        df = pd.concat([df,week_zero_df], ignore_index=True,)
        df = df.sort_values('Week', ascending=True)
        
        fig2 = px.line(df,x='Week',y='Total Wins', color = 'Team',template='gridiron_ink',line_shape = 'spline', title = 'Win Progression')
        fig2.update_xaxes(dtick=1,
                        tickfont=dict(
                size=18,         # Font size
            ))
        fig2.update_yaxes(dtick=1)
        fig2.update_layout(width=None, height=800)
        # Adjust the thickness of the lines
        fig2.update_traces(line=dict(width=4))  # Set the line width (e.g., 3 pixels)
        fig2.update_layout(legend=LEGEND_STD)


        # Customize the y-axis labels
        fig2.update_yaxes(
            tickfont=dict(
                size=20,         # Font size
            )
        )

        fig2.update_layout(uniformtext_minsize=10, uniformtext_mode='hide')

        # Update x-axis and y-axis titles with font customization
        fig2.update_layout(
            xaxis_title="Week",  # Set x-axis title
            yaxis_title="Wins",   # Set y-axis title
            xaxis=dict(
                title_font=dict(
                    size=20          # Set font size for x-axis title
                )
            ),
            yaxis=dict(
                title_font=dict(
                    size=20          # Set font size for y-axis title
                )
            )
        )
        
        # Determine final wins and sort by them
        final_scores = [(d.name, d.x[-1], d.y[-1], d.line.color) for d in fig2.data]
        final_scores.sort(key=lambda x: -x[2])  # Sort by final win count, descending

        # Define a list of potential text positions to avoid overlap
        text_positions = ['middle right','top right', 'bottom right', 'top left', 'bottom left', 'middle left','top center','bottom center']

        previous_score = None
        position_index = 0

        for team_name, x_final, y_final, color in final_scores:
            if y_final == previous_score:
                # Cycle through text positions to avoid overlap if scores are the same
                position_index = (position_index + 1) % len(text_positions)
            else:
                position_index = 0  # Reset position index when score changes

            text_position = text_positions[position_index]
            previous_score = y_final

            fig2.add_scatter(
                x=[x_final], y=[y_final],
                mode='markers+text',
                text=[team_name],
                textfont=dict(color=color, size=14, weight = 'bold'),
                textposition=text_position,
                marker=dict(color=color, size=12),
                showlegend=False
                )    
        fig2.update_layout(margin=dict(l=80, r=80, t=120, b=80))  # Set left, right, top, bottom padding within the plot area

        fig2.update_layout(xaxis=dict(range=[0, week + 1.5]))
        fig2.update_layout(title = dict(y=.93)
        )

        fig2.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Week %{x}<br>Wins: <b>%{y}</b><extra></extra>",
            selector=dict(type='scatter', mode='lines'),
        )
        fig2.update_layout(transition=dict(duration=400, easing='cubic-in-out'))

        apply_logo_to_fig(fig2)

        return fig2

    def LuckChart(self, current_week):
        
        self.WeeklyWins(current_week)
        df_wins = self.ConcatinatedWeeks
        

        df_week = df_wins[df_wins['Week'] == current_week]
        topscore = df_week['Score YTD'].max()
        topopponent = df_week['Opp YTD'].max()
        minscore = df_week['Score YTD'].min()
        minopponent = df_week['Opp YTD'].min()

        figScat = px.scatter(df_week, x="Opp YTD",y = 'Score YTD',size ="Total Wins", template = 'gridiron_ink', color = 'Team', text = 'Team',title=f'<b>Lucky Squares</b><br><sup>Week {current_week}</sup>', color_discrete_map=self.teamcolors)
        figScat.update_layout(width=800, height=800)


        # Calculate median values
        median_score = df_week['Score YTD'].median() #y value
        median_opp = df_week['Opp YTD'].median() #x value
        
        # Add horizontal and vertical lines to divide the plot into quadrants
        figScat.add_shape(type="line", x0=median_opp, x1=median_opp, 
                    y0=df_week['Score YTD'].min()-15, y1=df_week['Score YTD'].max()+15
                    , opacity=0.5,
                    line=dict(color="gold", width=2, dash="dash"))

        figScat.add_shape(type="line", x0=df_week['Opp YTD'].min()-15, x1=df_week['Opp YTD'].max()+15, 
                    y0=median_opp, y1=median_opp, opacity=0.5,
                    line=dict(color="gold", width=2, dash="dash"))

        figScat.update_traces(textposition='top center')
        figScat.update_traces(textfont_size=15,textfont=dict(weight='bold',  # Font family
                size=15   # Font color
            ))
        figScat.update_layout(showlegend=False)
        # Add the diagonal line
        #figScat.update_layout(shapes = [{'type': 'line', 'yref': 'paper', 'xref': 'paper', 'y0': 0, 'y1': 1, 'x0': 0, 'x1': 1}])

        # Add text to each corner
        figScat.add_annotation(x=0, y=0, text="Bad but Lucky", showarrow=False, xref="paper", yref="paper",font=dict(
                    family="Courier New, monospace",
                    size=20,
                    color=LABEL_COLOR
                    ), bgcolor='rgba(26,58,82,0.7)')
        figScat.add_annotation(x=1, y=0, text="Bad & Unlucky", showarrow=False, xref="paper", yref="paper",font=dict(
                    family="Courier New, monospace",
                    size=20,
                    color=LABEL_COLOR
                    ), bgcolor='rgba(26,58,82,0.7)')
        figScat.add_annotation(x=0, y=1, text="Good & Lucky", showarrow=False, xref="paper", yref="paper",font=dict(
                    family="Courier New, monospace",
                    size=20,
                    color=LABEL_COLOR
                    ), bgcolor='rgba(26,58,82,0.7)')
        figScat.add_annotation(x=1, y=1, text="Good & Tested", showarrow=False, xref="paper", yref="paper",font=dict(
                    family="Courier New, monospace",
                    size=20,
                    color=LABEL_COLOR
                    ), bgcolor='rgba(26,58,82,0.7)')
        figScat.update_layout(
            xaxis_title="Points Against",
            yaxis_title="Points For",
            xaxis=dict(
                title_font=dict(color='#F94144', shadow='none')
            ),
            yaxis=dict(
                title_font=dict(color='#90BE6D', shadow='none')
            )
        )

        figScat.update_yaxes(dtick=100,
                        tickfont=dict(
                size=16, family='Courier New',
            ))
        figScat.update_xaxes(dtick=100,
                        tickfont=dict(
                size=16, family='Courier New',
            ))
        figScat.add_annotation(
        text="O Size = Wins | --- = Avg",
        xref="paper", yref="paper",
        x=0.5, y=1.15, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=12,
        )
        )
        
        
        figScat.update_layout(xaxis=dict(range=[minopponent - 30, topopponent + 40]))
        figScat.update_layout(yaxis=dict(range=[minscore - 25, topscore + 25]))

        figScat.update_layout(margin=dict(t=80, b=100, l=100, r=100))

        figScat.update_layout(title=dict(y=.9))
        figScat.update_traces(
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Points For: <b>%{y:.1f}</b><br>"
                "Points Against: <b>%{x:.1f}</b><br>"
                "Wins: <b>%{marker.size}</b><extra></extra>"
            )
        )
        figScat.update_layout(transition=dict(duration=600, easing='elastic-in-out'))
        apply_logo_to_fig(figScat)
        return figScat

    def MatchupPreview_WinPercentage(self, PreviewWeek, Alternate=None):
        
        breakoutDF = self.Breakout_dict[PreviewWeek]
        
        
        # # Set Time Ticks
        # time_dict = {'Monday 7 PM': 'MON 7PM', 'Sunday 9 AM':'SUN 9AM', 'Sunday 1 PM':'SUN 1PM', 'Sunday 4 PM': 'SUN 4PM', 'Sunday 8 PM':'SUN 8PM',
        #         'Thursday 8 PM':'THU 8PM', 'Monday 8 PM':'MON 8PM','Thursday 4 PM':'THU 4PM','Thursday 12 PM':'THU 12PM','Friday 3 PM':'FRI 3PM'}
    
        # time_order = ['THU', 'SUN 9AM','SUN 1PM', 'SUN 4PM', 'SUN 8PM', 'MON 7PM', 'MON 8PM']
        
        # if Alternate == 'SundayMorning':
        #     time_order = ['THU 8PM', 'SUN 9AM','SUN 1PM', 'SUN 4PM', 'SUN 8PM', 'MON 8PM']
        # elif Alternate == 'Thanksgiving':
        #     time_order = ['THU 12PM', 'THU 4PM','THU 8PM','FRI 3PM','SUN 1PM', 'SUN 4PM', 'SUN 8PM', 'MON 8PM']
        # if Alternate == None:
        #     time_order = ['THU 8PM','SUN 1PM', 'SUN 4PM', 'SUN 8PM', 'MON 8PM']
        
        #Set-up Data
        breakoutDF['color'] = breakoutDF['team'].map(self.teamcolors)
        breakoutDF = breakoutDF.sort_values('gametime_gameday')
        self.GametimeList = breakoutDF['gametime_gameday_format'].unique()

        breakoutDF_group = breakoutDF.groupby(['team','gametime_gameday_format','matchup']).size().reset_index(name='count')
        #breakoutDF_group['GameTime-Simp'] = breakoutDF_group['gametime_gameday_format'].map(time_dict)
        grouped = breakoutDF_group.groupby('matchup')

        




        
        # Create a subplot with 1 row and 2 columns (for the bar chart and the pie chart)
        figCombo = make_subplots(
                rows=6, cols=2, 
                shared_xaxes=True,
                column_widths=[0.85, 0.15],  # Adjust the width of each subplot
                specs=[[{"type": "bar"}, {"type": "pie"}],
                    [{"type": "bar"}, {"type": "pie"}],
                    [{"type": "bar"}, {"type": "pie"}],
                    [{"type": "bar"}, {"type": "pie"}],
                    [{"type": "bar"}, {"type": "pie"}],
                    [{"type": "bar"}, {"type": "pie"}]]
                #subplot_titles=['Matchup Schedule','Win History']# Specify the chart types
            )
        row_ys = {1: 1, 2: 0.83, 3: 0.66, 4: 0.49, 5: 0.32, 6: 0.15}  # Adjust as needed
        
        OppWinPercentageTable_Current = All_Time.OppWinPercentageTable()
        for i in range(1,7):
            
            testgroup = grouped.get_group(i)

            teams = testgroup['team'].unique()
            win_mean = OppWinPercentageTable_Current.loc[teams[0], teams[1]]




            # Add the bar chart to the first column
            figCombo.add_trace(
                go.Bar(
                    y=testgroup['count'], 
                    x=testgroup['gametime_gameday_format'], 
                    marker=dict(
                        color = [self.teamcolors[team] for team in testgroup['team']], 
                        cornerradius = 10
                    ),
                    text=testgroup['count'],
                    textangle = 0,
                    textposition='auto',
                    showlegend=False,
                ),
                row=i, col=1
            )

            # Add the pie chart to the second column
            figCombo.add_trace(
                go.Pie(values=[win_mean, 1-win_mean] ,labels=[f'{teams[0]}',f'{teams[1]}'],
                    marker = dict(colors = [self.teamcolors[teams[0]],self.teamcolors[teams[1]]]), showlegend=False),
                row=i, col=2
            )
                # Create a custom title with colored team names
            title_html = f'<span style="color:{self.teamcolors[teams[0]]}">{teams[0]}</span> vs <span style="color:{self.teamcolors[teams[1]]}">{teams[1]}</span>'

            # Add the custom title as an annotation at the top of each subplot
            figCombo.add_annotation(
                text=title_html,  # The HTML title
                xref=f'x domain', yref=f'y domain',
                x=.5, y=1.2,  # Position it above the subplot (y > 1)
                xanchor='center',
                font=dict(size=15, weight ='bold'),
                showarrow=False,
                row=i, col=1  # Apply to the i-th row and first column (bar chart)
            )
            # Update the layout with dark theme and grouped bar mode
            figCombo.update_layout(barmode="group", template="gridiron_ink")
            figCombo.update_xaxes(
                # categoryorder="array",
                # categoryarray=time_order,
                showticklabels = True, 
                side = 'bottom',
                row=i, col=1  # Apply to the bar chart in the i-th row and first column
            )
            

        # Show the figure
        figCombo.update_layout(width=800, height=1200, title_text = f'<b>Week {PreviewWeek} Preview</b>')
        figCombo.update_xaxes(title_text="", side = 'bottom',tickfont=dict(size=14),
                                 ticktext=breakoutDF['Tick'], tickvals = breakoutDF['gametime_gameday_format'])
        figCombo.update_layout(xaxis=dict(categoryorder='array',categoryarray =self.GametimeList))
        figCombo.update_annotations(font_size = 20)

        figCombo.add_annotation(
                text=f'<b>Game Time Schedule</b>',  # The HTML title
                xref=f'paper', yref=f'paper',
                x=.4, y=1.06,  # Position it above the subplot (y > 1)
                xanchor='center',
                font=dict(size=26),
                showarrow=False,
            )
        figCombo.add_annotation(
                text=f'<b>Win History</b>',  # The HTML title
                xref=f'paper', yref=f'paper',
                x=.93, y=1.06,  # Position it above the subplot (y > 1)
                xanchor='center',
                font=dict(size=26),
                showarrow=False,
            )
        figCombo.update_traces(textfont=dict(
                        size=18, weight = 'bold'))
        # figCombo.update_xaxes(tickfont=dict(size=12))
        figCombo.update_yaxes(dtick=2)
        figCombo.update_layout(uniformtext_minsize=10, uniformtext_mode='hide')
        
        figCombo.update_layout(
                                margin=dict(t=150, b=40, l=60, r=60)  # Adjust these values as needed
                                )

        apply_logo_to_fig(figCombo,xval=0,yval=1.1)
        
        return figCombo
       
    def PlayerPoints(self, WeekNum):
        self.WeeklyWins()    

        figScoreLine = px.line(self.ConcatinatedWeeks[self.ConcatinatedWeeks['Week'].isin(range(0, WeekNum+1))], x='Week',y='Total', template='gridiron_ink', facet_col='Team',markers=True,facet_col_wrap=4, color='Team', line_shape='spline', color_discrete_map=self.teamcolors)
        figScoreLine.update_layout(xaxis_title="", yaxis_title="")
        figScoreLine.update_layout(width=None, height=1000, showlegend=False)
        figScoreLine.update_layout(title=dict(text=f"{self.year} Score Trends",y=.91))
        figScoreLine.update_annotations(font_size=20)
        
        # Customize facet titles
        figScoreLine.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        
        figScoreLine.update_xaxes(tickfont=dict(size=13),)
        figScoreLine.update_yaxes(tickfont=dict(size=13))

        figScoreLine.update_xaxes(title_text="", col=1)
        figScoreLine.update_xaxes(title_text="", col=2)
        figScoreLine.update_xaxes(title_text="", col=3)
        figScoreLine.update_xaxes(title_text="", col=4)
        figScoreLine.update_yaxes(title_text="", col=1)
        figScoreLine.update_xaxes(matches=None,side = 'bottom',tickvals = [5, 10, 15])
        figScoreLine.for_each_xaxis(lambda xaxis: xaxis.update(showticklabels=True))
        

        figScoreLine.update_layout(
                                margin=dict(t=160, b=80, l=60, r=60)  # Adjust these values as needed
                                )
        apply_logo_to_fig(figScoreLine,xval=0,yval=1.1)

        for ann in figScoreLine.layout.annotations:
            if ann.text in self.teamcolors:
                ann.font.color = self.teamcolors[ann.text]

        return figScoreLine
    
    def WeeklyWinsGraphBreakout(self,week):
        self.WeeklyWins()
        df = self.ConcatinatedWeeks

        fig2 = px.line(df,x='Week',y='Total Wins', color = 'Team',template='gridiron_ink',line_shape = 'spline', facet_col='Team',facet_col_wrap=3, title = '<b>Weekly Wins</b><br><sup>Breakout</sup>', color_discrete_map=self.teamcolors)
        
        
        fig2.update_yaxes(zerolinewidth = 1, ticklabelposition = 'inside',ticklabelstandoff=130, tickfont = dict(size = 12), dtick = 2,showticklabels=True,showgrid=True)
        fig2.update_xaxes(zerolinewidth = 1,side = 'bottom', ticklabelposition = 'inside bottom', tickfont = dict(size =12), dtick = 1, showticklabels=True,showgrid=False)
        

        
        fig2.update_layout(width=900, height=900, showlegend=False, title = dict(y=.93))
        
        # Adjust the thickness of the lines
        fig2.update_traces(line=dict(width=4))  # Set the line width (e.g., 3 pixels)
        
        fig2.update_layout(legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title = ''
        ))


        # Update x-axis and y-axis titles with font customization
        fig2.update_layout(
            xaxis_title="",  
            yaxis_title="",  
            xaxis=dict(
                title_font=dict(
                    size=20          # Set font size for x-axis title
                )
            ),
            yaxis=dict(
                title_font=dict(
                    size=20          # Set font size for y-axis title
                )
            )
        )
        fig2.update_layout(
            xaxis2_title="",  
            yaxis2_title="",  
            xaxis2=dict(
                title_font=dict(
                    size=20          # Set font size for x-axis title
                )
            ),
            yaxis2=dict(
                title_font=dict(
                    size=20          # Set font size for y-axis title
                )
            )
        )
        fig2.update_layout(
            xaxis3_title="",  
            yaxis3_title="",  
            xaxis3=dict(
                title_font=dict(
                    size=20          # Set font size for x-axis title
                )
            ),
            yaxis3=dict(
                title_font=dict(
                    size=20          # Set font size for y-axis title
                )
            )
        )
        
        # Determine final wins and sort by them
        final_scores = [(d.name, d.x[-1], d.y[-1], d.line.color) for d in fig2.data]
        final_scores.sort(key=lambda x: -x[2])  # Sort by final win count, descending

       

        fig2.update_layout(xaxis=dict(range=[0, week + 1.5])) 
        fig2.update_layout(yaxis=dict(range=[0, week + 1])) 
        fig2.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig2.update_layout(
        font=dict(
            size=18,  # Set the font size here
        )
    )
        fig2.update_yaxes(title="", col =1)  # Set a new title for all y-axes

        for annotation in fig2.layout.annotations:
                    title_text = annotation.text  # e.g., "Team A vs Team B"
                    #teams = title_text.split(" vs ")  # Split into individual team names
                    # Create a styled title with team names in respective colors
                    annotation.text = f"<span style='color:{self.teamcolors[title_text]}'>{title_text}</span>"
                    annotation.font.size = 23  # Optional: Adjust font size for clarity
        
        fig2.update_layout(
                                margin=dict(t=130, b=80, l=60, r=60)  # Adjust these values as needed
                                )
        apply_logo_to_fig(fig2,xval=0,yval=1.1)
        
        return fig2
 
    def ScoreFrequencyGraph(self, WeekNum):
        figScoring = px.histogram(self.Matches[self.Matches['Week'].isin(range(0,WeekNum+1))], x='Total', template='gridiron_ink',title = 'Scoring Frequency', marginal='rug',
                                  color = 'Team', labels = 'Team', color_discrete_map=self.teamcolors)
        figScoring.update_layout(width=None, height=800)
        figScoring.update_yaxes(
                tickfont=dict(
                    size=15,         # Font size
                ),
                title = None,
                
            )
        figScoring.update_xaxes(
                tickfont=dict(
                    size=15,         # Font size
                ),
                title = None,
                dtick=10,
                side = 'bottom'
            )
        figScoring.update_layout(legend=LEGEND_STD)
        figScoring.update_traces(marker_line_width=2, marker_line_color='rgba(0,0,0,0.25)')
        figScoring.update_layout(showlegend = True, title = dict(y=.93))

        figScoring.update_traces(
            hovertemplate="Score range: <b>%{x}</b><br>Weeks in range: <b>%{y}</b><extra></extra>"
        )
        figScoring.update_layout(
                                margin=dict(t=130, b=40, l=75, r=75)
                                )
        apply_logo_to_fig(figScoring, yval=-0.09)
        return figScoring
        
    def StarterPerformanceGraph(self):
        df = self.BreakoutSeason
        Starters = df[df['starter'] == 1]
        PositionPoints = Starters.groupby(['team','position'])['points'].sum()
        PositionPoints = PositionPoints.reset_index()
        PositionPoints = round(PositionPoints,0)
        
        
        figPosTotals = px.bar(PositionPoints, x='points',y='team', color = 'position', template = 'gridiron_ink', orientation='h', 
                      text='points',title = 'Starter Points by Position',
                      category_orders={'position':['QB','RB','WR','TE','K','DEF']})
        figPosTotals.update_yaxes(
                tickfont=dict(
                    size=20,         # Font size
                ),
                title = None,
                categoryorder="total ascending",
            )
        figPosTotals.update_layout(width=800, height=1200)
        figPosTotals.update_traces(textfont_size=16, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(size=16))
        figPosTotals.update_traces(marker_line_width=2,marker_line_color='rgba(0,0,0,0.25)')
            
        figPosTotals.update_traces(insidetextanchor= 'middle')
        figPosTotals.update_layout(
                uniformtext_minsize=10,
                uniformtext_mode='show'
                )
        # Update the legend title
        figPosTotals.update_layout(
            legend=dict(
                title=dict(
                    text=None,
                    font=dict(
                        size=25,
                        
                    )
                )
            )
        )  
        
        
        figPosTotals.update_xaxes(
                tickfont=dict(
                    size=20,         # Font size
                ),
                title = None
            )
        
        figPosTotals.update_layout(legend=dict(orientation="h"), showlegend = True)
        # Set legend location
        figPosTotals.update_layout(
            legend=dict(
                x=0.4,  # x-coordinate of the legend (0 to 1, where 0 is left and 1 is right)
                y=1.07,   # y-coordinate of the legend (0 to 1, where 0 is bottom and 1 is top)
                xanchor="center",  # horizontal anchor point ('left', 'center', 'right')
                yanchor="top" ,   # vertical anchor point ('top', 'middle', 'bottom')
                font = dict(size = 16)
            )
        )

        figPosTotals.update_layout(
                                margin=dict(t=140, b=100, l=180, r=40)  # Adjust these values as needed
                                )
        apply_logo_to_fig(figPosTotals, xval=.4)

        return figPosTotals

    def ViolinPlayer(self, WeekNum,Starters = False):
        WeekRange = range(0,WeekNum+1)
        if Starters == False:
            df = self.BreakoutSeason[self.BreakoutSeason['week_x'].isin(WeekRange)]
            titleText = "<b>Positional Points Distribution</b><br><sup>Players</sup>"
        else:
            df = self.Starters[self.Starters['week_x'].isin(WeekRange)]
            titleText = "<b>Positional Points Distribution</b><br><sup>Starting Players</sup>"

        if df.empty:
            fig = go.Figure()
            fig.update_layout(template='gridiron_ink',
                              annotations=[dict(text='No data for this week range', x=0.5, y=0.5,
                                                showarrow=False, font=dict(size=16, color='#BDE2FF'),
                                                xref='paper', yref='paper')],
                              xaxis_visible=False, yaxis_visible=False)
            return fig

        figViolin = px.violin(df, x='points', y='position', facet_col='team', facet_col_wrap=3, color='position',
                              template='gridiron_ink',
                              category_orders={"position": ["QB", "RB", "WR", "TE", "K", "DEF"]})
        figViolin.update_traces(orientation='h', side='positive', width=3, points=False, spanmode='hard')
        figViolin.update_layout(
            title=dict(text=titleText)
        )
        figViolin.update_layout(width=800, height=1200)
        figViolin.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        figViolin.update_annotations(font_size=25)

        figViolin.for_each_xaxis(lambda xaxis: xaxis.update(showticklabels=True))
        figViolin.update_yaxes(
                showticklabels=True,
                matches=None,
                categoryorder='array',
                categoryarray=["QB", "RB", "WR", "TE", "K", "DEF"],
                tickfont=dict(
                    size=20,
                ),
                title=None
            )
        figViolin.update_xaxes(
                tickfont=dict(
                    size=13,
                ),
                title=None,
                side = 'bottom'
            )
        for annotation in figViolin.layout.annotations:
            title_text = annotation.text
            color = self.teamcolors.get(title_text, '#BDE2FF')
            annotation.text = f"<span style='color:{color}'>{title_text}</span>"
            annotation.font.size = 25

        figViolin.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Score: <b>%{x:.2f}</b><extra></extra>"
        )
        figViolin.update_layout(
                                margin=dict(t=140, b=100, l=40, r=40)  # Adjust these values as needed
                                )
        apply_logo_to_fig(figViolin)
        return figViolin
    
    def ViolinPosition(self, Starters = True):
        
        if Starters == False:
            df = self.BreakoutSeason  
            titleText = "<b>Positional Points Distribution</b><br><sup>Position</sup>"
        else:
            df = self.Starters
            titleText = "<b>Positional Points Distribution</b><br><sup>Starters by Position</sup>"
        
        figViolin2 = px.violin(df,x='points', y='team',facet_col='position',facet_col_wrap=2, color = 'team', 
                       template='gridiron_ink',category_orders={
                           "position": ["QB", "RB", "WR", "TE", "K", "DEF"],
                              })
        figViolin2.update_traces(orientation='h', side='positive', width=3, points=False, spanmode='hard')
        figViolin2.update_layout(width=800, height=1200, showlegend=False,)
        figViolin2.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        figViolin2.for_each_xaxis(lambda xaxis: xaxis.update(showticklabels=True))
        figViolin2.update_yaxes(
                showticklabels=True,
                matches=None,
                tickfont=dict(
                    size=13,
                ),
                title=None
            )
        figViolin2.update_xaxes(
                tickfont=dict(
                    size=13,         # Font size
                ),
                title=None,
                side = 'bottom'
            )
        figViolin2.update_annotations(font_size=35, font=dict(color=TEXT_COLOR))
        figViolin2.update_layout(
            title=dict(text=titleText)
        )
        figViolin2.update_layout(
                                margin=dict(t=140, b=100, l=120, r=40)  # Adjust these values as needed
                                )
        apply_logo_to_fig(figViolin2)
        return figViolin2
        
    def TopPlayers(self, position, threshold):
        self.SetBest(threshold)
        df = self.Best
        TopPlayers = df[df['position'] == position]
        TopPlayers = TopPlayers[TopPlayers['TotalYTD']>threshold]

        figLine = px.line(TopPlayers,x='week_x',y='Score YTD', color = 'player',line_shape = 'spline',template='gridiron_ink',
                          title=f'Top {position}s over {threshold}')
        figLine.update_layout(width=None, height=800, title = dict(y=.93), showlegend = True)
        figLine.update_layout(legend=LEGEND_STD)
        figLine.update_yaxes(
                tickfont=dict(
                    size=20,         # Font size
                ),
                title=None
            )
        figLine.update_xaxes(
                tickfont=dict(
                    size=20,         # Font size
                ),
                title='Week',
                side = 'top'
            )
        figLine.update_layout(
                                margin=dict(t=150, b=100, l=60, r=60)
                                )
        apply_logo_to_fig(figLine)
        return figLine
    
    def PositionStrengthCalculator(self):
        scaler = MinMaxScaler()
        scalerStandard = StandardScaler()
        PosistionPolar = self.Starters.groupby(['team','position'])['points'].mean()
        self.PosistionPolar = PosistionPolar.reset_index()
        PosistionPivot = self.PosistionPolar.pivot(columns='position', index='team', values='points')
        PivotPositions = PosistionPivot.columns
        PivotTeams = PosistionPivot.index
        PosistionPivot_scaled = scaler.fit_transform(PosistionPivot)

        PosistionPivot_Standard_scaled = scalerStandard.fit_transform(PosistionPivot)
        
        self.PosistionPivot_scaled = pd.DataFrame(PosistionPivot_scaled, columns = PivotPositions, index=PivotTeams)
        self.PosistionPivot_Standard_scaled = pd.DataFrame(PosistionPivot_Standard_scaled, columns = PivotPositions, index=PivotTeams)

    def PositionStrengthHeatmap(self):
        """Heatmap of positional z-scores — positions on x-axis, teams on y-axis sorted by overall strength."""
        self.PositionStrengthCalculator()

        df = self.PosistionPivot_Standard_scaled.copy()

        # Raw avg pts per position per team (for annotation tooltip context)
        raw = self.PosistionPolar.pivot(columns='position', index='team', values='points').reindex(df.index)

        # Sort teams: best overall z-score sum at top
        df['_total'] = df.sum(axis=1)
        df = df.sort_values('_total', ascending=True)
        df = df.drop(columns='_total')

        # Position display order
        pos_order = [c for c in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'] if c in df.columns]
        df = df[pos_order]
        raw = raw.reindex(index=df.index, columns=pos_order)

        teams  = df.index.tolist()
        n_teams = len(teams)
        n_pos   = len(pos_order)

        z_vals  = df.values.tolist()
        raw_vals = raw.values

        # Build annotation text: z-score + raw avg pts
        text_matrix = []
        for i, team in enumerate(teams):
            row = []
            for j, pos in enumerate(pos_order):
                z   = df.iloc[i, j]
                avg = raw_vals[i, j] if not np.isnan(raw_vals[i, j]) else 0
                row.append(f'<b>{z:+.1f}σ</b><br>{avg:.1f} pts')
            text_matrix.append(row)

        team_colors = [self.teamcolors.get(t, '#BDE2FF') for t in teams]

        fig = go.Figure(go.Heatmap(
            z=z_vals,
            x=pos_order,
            y=teams,
            text=text_matrix,
            texttemplate='%{text}',
            textfont=dict(size=11, family='Courier New'),
            colorscale=[
                [0.0,  '#F94144'],  # strong red — well below average
                [0.35, '#C75B5E'],
                [0.5,  '#3D5E78'],  # neutral — league average
                [0.65, '#5B9E6D'],
                [1.0,  '#90BE6D'],  # strong green — well above average
            ],
            zmid=0,
            zmin=-2.5, zmax=2.5,
            showscale=True,
            colorbar=dict(
                title=dict(text='z-score', font=dict(color='#BDE2FF', family='Courier New', size=11)),
                tickfont=dict(color='#BDE2FF', family='Courier New', size=10),
                tickvals=[-2, -1, 0, 1, 2],
                ticktext=['-2σ', '-1σ', 'avg', '+1σ', '+2σ'],
                thickness=10,
                len=0.6,
                bgcolor='rgba(22,49,70,0.6)',
                bordercolor='#3D5E78',
                borderwidth=1,
            ),
            hovertemplate='<b>%{y}</b> · %{x}<br>z-score: <b>%{z:+.2f}σ</b><extra></extra>',
        ))

        # Colored y-axis tick labels per team
        ticktext = [f"<span style='color:{c}'><b>{t}</b></span>"
                    for t, c in zip(teams, team_colors)]

        fig.update_layout(
            template='gridiron_ink',
            width=None,
            height=max(480, n_teams * 52 + 80),
            margin=dict(t=20, b=60, l=200, r=20),
            xaxis=dict(
                side='top',
                tickfont=dict(size=13, family='Courier New', color='#BDE2FF'),
                tickangle=0,
            ),
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(n_teams)),
                ticktext=ticktext,
                tickfont=dict(size=12, family='Courier New'),
                automargin=True,
            ),
        )

        # Horizontal divider lines between teams
        for i in range(1, n_teams):
            fig.add_hline(y=i - 0.5, line=dict(color='#0d1e2e', width=1))

        return fig

    def PositionStrengthPolar(self):
        self.PositionStrengthCalculator()
        
        PosistionAvg = self.Starters.groupby('position')['points'].mean()
        PosistionPolar = round(self.PosistionPolar,2)
        PosistionAvg = round(PosistionAvg,2)
        PosistionPolar = PosistionPolar.reset_index()
        PosistionAvg = PosistionAvg.reset_index()
        PosistionPivot_scaled = self.PosistionPivot_scaled.reset_index()

        PosistionPivot_Standard_scaled = self.PosistionPivot_Standard_scaled.reset_index()
        teamlist = PosistionPivot_scaled.team.unique()
        teamdict = dict(enumerate(teamlist,1))
        teamlistorder = teamdict.values()
        rowlist = [1,1,1,2,2,2,3,3,3,4,4,4]
        collist = [1,2,3,1,2,3,1,2,3,1,2,3]
        rowdict = dict(enumerate(rowlist,1))
        coldict = dict(enumerate(collist,1))
        polars = ['polar']*12
        
        PosistionPivot_scaled = self.PosistionPivot_scaled
        PosistionPivot_Standard_scaled = self.PosistionPivot_Standard_scaled.reset_index()
        
        figPolarAll = make_subplots(rows=4, cols=3, specs=[[{'type': 'polar'}, {'type': 'polar'}, {'type': 'polar'}],[{'type': 'polar'}, {'type': 'polar'}, {'type': 'polar'}],
                                                   [{'type': 'polar'}, {'type': 'polar'}, {'type': 'polar'} ],[{'type': 'polar'}, {'type': 'polar'}, {'type': 'polar'} ]],
                            subplot_titles=list(teamlistorder)
                            )
        def _hex_to_rgba(hex_color, alpha=0.25):
            h = hex_color.lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f'rgba({r},{g},{b},{alpha})'

        for i in range (1,13):
            team_name = teamdict[i]
            team_color = self.teamcolors.get(team_name, '#BDE2FF')
            PolarTest = PosistionPivot_Standard_scaled[PosistionPivot_Standard_scaled['team']==team_name]
            PolarTest = PolarTest.set_index('team').T
            PolarTest.columns = ['points']
            PolarTest = PolarTest.reset_index()
            figPolarAll.add_trace(go.Scatterpolar(r=PolarTest['points'], theta=PolarTest['position'], mode='markers+text',textposition='top center',name=team_name,fill='toself', r0 = -2, dr = .5,
                                                  text=round(PolarTest['points'],1),
                                                  fillcolor=_hex_to_rgba(team_color),
                                                  line=dict(color=team_color, width=2),
                                                  marker=dict(color=team_color),
                                                  ), row=rowdict[i], col=coldict[i])
            
            

        figPolarAll.update_layout(width=800, height=1200, template = 'gridiron_ink', showlegend=False)
        figPolarAll.update_layout(polar1=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=0,  # Optional: Adjust tick angle for readability
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar2=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar3=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar4=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar5=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar6=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar7=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar8=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar9=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar10=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar11=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                polar12=dict(
                                    radialaxis=dict(
                                        range=[-3, 3],  # Set the radial range; adjust to fit your data scale
                                        tickvals=[-3,0,3],  # Customize tick values for consistency
                                        tickformat=".1f",  # Set the format for tick labels
                                        tickangle=45,
                                        showticklabels=False, tickfont=dict(color = '#163146')
                                    )),
                                )

        figPolarAll.update_layout(
            title="<b>Positional Strength</b><br><sup>Std Dev from Average</sup>",
            )
        
        for ann in figPolarAll.layout.annotations:
            team_name = ann.text
            ann.font.size = 22
            ann.font.color = self.teamcolors.get(team_name, TEXT_COLOR)
        figPolarAll.update_polars(bgcolor='#BDE2FF')
        
        figPolarAll.add_annotation(
            text="",
            xref="paper", yref="paper",
            x=-0.0, y=1.05, # Position relative to figure (right side, middle)
            showarrow=False,
            font=dict(
                size=18,
            )
            )
        figPolarAll.update_traces(textfont_size=13, textfont=dict(color = '#163146'))
        figPolarAll.update_traces(
            hovertemplate="<b>%{theta}</b><br>Strength: <b>%{r:.2f}</b><extra></extra>"
        )

        figPolarAll.update_layout(
                                margin=dict(t=140, b=100, l=60, r=60)  # Adjust these values as needed
                                )
        apply_logo_to_fig(figPolarAll)
        return figPolarAll
    
    
    def ForAgainstwithTeams(self):
        OpponentPoints = self.BreakoutSeason.groupby(['team','opponent_team'])['points'].sum().reset_index().sort_values('points', ascending=False)
        OpponentPointsNoTeam = self.BreakoutSeason.groupby(['team','opponent_team'])['points'].sum().round(1).reset_index().sort_values('points', ascending=False)
        OpponentPointsNoTeamTOP =  OpponentPointsNoTeam.iloc[0:10]
        OpponentPointsNoTeamTOP['TeamVs'] = OpponentPointsNoTeamTOP.team + ' vs. ' + OpponentPointsNoTeamTOP.opponent_team
        OpponentPointsNoTeamTOP['Purpose'] = 'Points Against...'    
        
        TeamPoints = self.BreakoutSeason.groupby(['team','recent_teams'])['points'].sum().round(1).reset_index().sort_values('points', ascending=False)
        TeamPointsTOP = TeamPoints.iloc[0:10]
    
        TeamPointsTOP['color'] = TeamPointsTOP.team.map(self.teamcolors)
        OpponentPointsNoTeamTOP['color'] = OpponentPointsNoTeamTOP.team.map(self.teamcolors)
        TeamPointsTOP['TeamVs'] = TeamPointsTOP.team + ' w/ ' + TeamPointsTOP.recent_teams
        TeamPointsTOP['Purpose'] = 'Points With...'

        figTeamPoints = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=False,
                    vertical_spacing=.1,
                    specs=[[{"type": "bar"}],
                            [{"type": "bar"}]],
                    subplot_titles=['Points With...','Points vs...']
                )
        figTeamPoints.add_trace(
                    go.Bar(
                        x=TeamPointsTOP['points'],
                        y=TeamPointsTOP['TeamVs'],
                        text=TeamPointsTOP['points'],
                        textangle=0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h',
                        marker_color=TeamPointsTOP['color'],
                        opacity=.8,
                        textfont=dict(size=24)
                    ),
                    row=1, col=1
                )
        figTeamPoints.add_trace(
                    go.Bar(
                        x=OpponentPointsNoTeamTOP['points'],
                        y=OpponentPointsNoTeamTOP['TeamVs'],
                        text=OpponentPointsNoTeamTOP['points'],
                        textangle=0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h',
                        marker_color=OpponentPointsNoTeamTOP['color'],
                        opacity=.8,
                        textfont=dict(size=24)
                    ),
                    row=2, col=1
                )

        figTeamPoints.update_layout(height = 1200, width = 900, template = 'gridiron_ink', barcornerradius = 7)
        
        figTeamPoints.update_annotations(font_size=25)
        figTeamPoints.update_xaxes(side='bottom')
        figTeamPoints.update_layout(title="<b>Points With & Against NFL Team</b>")

        figTeamPoints.update_annotations(font=dict(color=TEXT_COLOR))
        figTeamPoints.update_layout(margin=dict(t=100, b=100, l=220, r=40))

        apply_logo_to_fig(figTeamPoints,xval=.40, yval=-0.06)

        return figTeamPoints

    def StatusGraph(self,WeekObj):
        self.Calc(WeekObj)
        self.PowerRankings(WeekObj.week)
        teams = list(self.PowerRanks[self.PowerRanks['Week'] == WeekObj.week].sort_values('Power Ranking').Team)
        LeagueAverage = self.StatusDict['LeagueAverage']

        Scores = self.StatusDict['Scores']
        AverageScores = self.StatusDict['AverageScores']
        PowerRanks = self.StatusDict['PowerRanks']
        PreviousRanks = self.StatusDict['PreviousRanks']
        PowerPercents = self.StatusDict['PowerPercents']
        OptimalScores = self.StatusDict['OptimalScores']

        
        fig = go.Figure()

        y1 = 1.08
        y2 = 1.0
        
        
        for team in teams:


            y1 -= .08
            y2 -= .08
            

            fig.add_trace(go.Indicator(
                mode="gauge+number",
                value=Scores[team],
                title={'text': f"{team}",'font':{'size' : 25,'color' : self.teamcolors[team]}},
                domain={'x': [.1, .3], 'y': [y2, y1]},
                number = {'font':{'size': 18}},
                gauge={
                    'axis': {'range': [None, OptimalScores[team]], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': LABEL_COLOR}, # Color of the manager's score bar
                    'shape':'bullet',
                    'borderwidth': 4,
                    'bar':{'thickness': .6, 'color' : 'rgba(148,103,189,.8)'},
                    'threshold' : dict(value = OptimalScores[team]),

                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, OptimalScores[team] * .7], 'color': '#F94144'},   # Poor
                        {'range': [OptimalScores[team] * .7, OptimalScores[team] * .9], 'color': '#E6DB74'},  # Average
                        {'range': [OptimalScores[team] * .9, OptimalScores[team]], 'color': '#90BE6D'}  # Good
                    ],
                }
            ))
            fig.add_trace(go.Indicator(
                mode="number",
                value= Scores[team]/OptimalScores[team],
                #title={'text': f"Efficiency"},
                domain={'x': [0.1, .25], 'y': [y2, y1]},
                number =dict(valueformat = ".0%", suffix = ' Efficient')

            ))

            fig.add_trace(go.Indicator(
                mode = "delta", value = Scores[team],
                domain = {'x': [.35, .45], 'y': [y2, y1]},
                delta = {'reference': AverageScores[team], 'position': "left", 'font':{'size': 40},'decreasing':dict(color='#F94144'),'increasing':dict(color='#90BE6D')}
                #'suffix':f' pts <br>vs Personal Average'
            )
            )

            fig.add_trace(go.Indicator(
                mode = "delta", value = Scores[team],
                domain = {'x': [.5, .6], 'y': [y2, y1]},
                delta = {'reference': LeagueAverage, 'position': "left",'decreasing':dict(color='#F94144'),'increasing':dict(color='#90BE6D'),
                         'font':{'size': 40}},

            ))

            fig.add_trace(go.Indicator(
                mode="number+delta",
                value=PowerRanks[team],
                domain={'x': [0.6, .9], 'y': [y2, y1]},
                number =dict( suffix = ''),    
                delta = {'reference': PreviousRanks[team], 'position': "bottom",'decreasing':dict(color='#90BE6D', symbol = '↑'),'increasing':dict(color='#F94144', symbol = '↓'),
                          'suffix':' vs Last Week','valueformat' : "0",}


            ))

            fig.add_trace(go.Indicator(
                mode="number",
                value=PowerPercents[team],
                #title={'text': f"Power Win %"},
                domain={'x': [0.9, 1], 'y': [y2, y1]},
                number =dict( suffix = '', valueformat = ".0%"),    
                
            ))

            fig.update_layout(
                title_text=f'Power & Efficiency<br><sup>Week {WeekObj.week}</sup>',
                template='gridiron_ink'
            )
        # fig.add_annotation(
        # text="Efficiency",
        # xref="paper", yref="paper",
        # x=.1, y=1.05, # Position relative to figure (right side, middle)
        # showarrow=False,
        # font=dict(
        #     size=25,
        #     color="gold"
        # )
        # )

        fig.add_annotation(
        text="Vs.<br>Personal Avg.",
        xref="paper", yref="paper",
        x=.4, y=1.05,
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR
        )
        )

        fig.add_annotation(
        text=f"Vs.<br>League Avg.<br><sup>[{int(LeagueAverage)} pts.]</sup>",
        xref="paper", yref="paper",
        x=.55, y=1.05,
        showarrow=False,
        font=dict(
            size=15,
            color=LABEL_COLOR
        )
        )

        fig.add_annotation(
        text="Power Rankings",
        xref="paper", yref="paper",
        x=.83, y=1.05,
        showarrow=False,
        font=dict(
            size=25,
            color=LABEL_COLOR
        )
        )

        fig.add_annotation(
        text="Power Win %",
        xref="paper", yref="paper",
        x=1.02, y=1.05,
        showarrow=False,
        font=dict(
            size=25,
            color=LABEL_COLOR
        )
        )

        fig.update_layout(margin=dict(t=130, b=100, l=120, r=40))
        fig.update_layout(title = dict(y=.95))
        
        apply_logo_to_fig(fig)
        
        return fig
    
    def SeasonPointsForAgainst(self):

        df = self.Matches
        df_group = df.groupby('Team')[['Total','Opp']].sum().round(0)
        df_group['Opp'] = df_group['Opp'] * -1
        df_group['Dif'] = df_group['Total'] + df_group['Opp']
        df_group['Total_Rank'] = df_group['Total'].rank(ascending=False)
        df_group['Opp_Rank'] = df_group['Opp'].rank(ascending=True)

        df_group.sort_values('Dif',ascending=False)




        figTotal = px.bar(df_group.reset_index(),x=['Total','Opp','Dif'], y = 'Team', barmode= 'overlay', text_auto=True, title=f"<b>For & <span style='color:#17BECF'>Against</span></b>")
        figTotal.update_layout( xaxis={'title': None},
                                        yaxis={'categoryorder':'total ascending','title': None}
                                        )
        figTotal.update_xaxes(
                        tickfont=dict(
                            size=16,         # Font size
                        ),
                        title = None
                    )

                    # Customize the y-axis labels
        figTotal.update_yaxes(
                        tickfont=dict(size=16, weight='bold'),
                        title=None
                    )
        figTotal.update_traces(insidetextanchor= 'middle',textfont=dict(
                        size=35, weight = 'bold'))

        figTotal.update_layout(margin=dict(t=130, b=100, l=230, r=40))
        figTotal.update_layout(title = dict(y=.93))

        figTotal.update_traces(
            hovertemplate="<b>%{y}</b><br>%{fullData.name}: <b>%{x:.1f}</b><extra></extra>"
        )
        figTotal.update_layout(transition=dict(duration=500, easing='cubic-in-out'))

        self.UpdateColors(figTotal)

        apply_logo_to_fig(figTotal)

        return figTotal
    
    def BrawnyBench(self):
        BrawnyBench = self.BreakoutSeason

        BrawnyBench = BrawnyBench[BrawnyBench.starter == 0]
        BrawnyBenchGroup = BrawnyBench.groupby(['team'])['points'].sum().round(0).reset_index().sort_values('points')
        BrawnyBenchGroup['color'] = BrawnyBenchGroup['team'].map(self.teamcolors)

        figBench = px.bar(BrawnyBenchGroup, x = 'points',y = 'team', text = 'points',title = '<b>Brawny Benches</b><br><sup>Points That Just Sat There</sup>', 
                          color = 'team',color_discrete_map=self.teamcolors)
        figBench.update_layout(
                            margin = dict(l=220),
                            xaxis = dict(title = "",tickfont = dict(size = 22)),
                            yaxis = dict(title = '',tickfont = dict(size = 22)),
                            title = dict(y = 0.95, font= dict(size = 45))
                            )
        figBench.update_traces(textposition='inside', textfont_size=80)
        apply_logo_to_fig(figBench, xval = 0.43)
        # self.UpdateColors(figBench)


        return figBench

    def EPAScatter(self):
        """Scatter: total EPA (starters) vs fantasy score per team per week, with regression line."""
        if self.BreakoutSeason is None or self.BreakoutSeason.empty:
            return go.Figure()

        starters = self.BreakoutSeason[self.BreakoutSeason['starter'] == 1].copy()

        # Find all numeric EPA columns
        epa_cols = [c for c in starters.columns if 'epa' in c.lower()
                    and starters[c].dtype in ['float64', 'float32', 'int64']]
        if not epa_cols:
            fig = go.Figure()
            fig.update_layout(
                template='gridiron_ink',
                annotations=[dict(text='EPA data not available', x=0.5, y=0.5,
                                  showarrow=False, font=dict(size=16, color='#BDE2FF'),
                                  xref='paper', yref='paper')],
            )
            return fig

        starters['_total_epa'] = starters[epa_cols].sum(axis=1)
        grp = starters.groupby(['team', 'week_NFL']).agg(
            total_epa=('_total_epa', 'sum'),
            fantasy_pts=('points', 'sum'),
        ).reset_index()

        grp['label'] = grp['team'] + ' Wk' + grp['week_NFL'].astype(int).astype(str)

        fig = px.scatter(
            grp, x='total_epa', y='fantasy_pts', color='team',
            color_discrete_map=self.teamcolors,
            template='gridiron_ink',
            labels={'total_epa': 'Total EPA (Starters)', 'fantasy_pts': 'Fantasy Points Scored'},
            trendline='ols',
        )
        fig.update_traces(
            text=grp['label'],
            textposition='top center',
            hovertemplate='<b>%{text}</b><br>EPA: <b>%{x:.1f}</b><br>Pts: <b>%{y:.1f}</b><extra></extra>',
            selector=dict(mode='markers'),
        )
        fig.update_traces(
            hovertemplate='Trend<extra></extra>',
            selector=dict(type='scatter', mode='lines'),
        )
        fig.update_layout(showlegend=True, margin=dict(b=100))
        fig.update_xaxes(title_standoff=40, tickfont_size=10)
        fig.update_yaxes(title_standoff=15)
        return fig

    def WOPRTreemap(self, week=None):
        """Treemap of WR/TE starters sized by WOPR (or target_share/targets if wopr absent)."""
        if self.BreakoutSeason is None or self.BreakoutSeason.empty:
            return go.Figure()

        starters = self.BreakoutSeason[
            (self.BreakoutSeason['starter'] == 1) &
            (self.BreakoutSeason['position'].isin(['WR', 'TE']))
        ].copy()

        if week is not None:
            starters = starters[starters['week_NFL'] == float(week)]

        # Find best available opportunity metric
        size_col = None
        for candidate in ['wopr', 'wopr_x', 'target_share', 'targets']:
            if candidate in starters.columns:
                size_col = candidate
                break

        if size_col is None or starters.empty:
            fig = go.Figure()
            fig.update_layout(
                template='gridiron_ink',
                annotations=[dict(text='WOPR/target data not available', x=0.5, y=0.5,
                                  showarrow=False, font=dict(size=16, color='#BDE2FF'),
                                  xref='paper', yref='paper')],
            )
            return fig

        starters = starters[starters[size_col].notna() & (starters[size_col] > 0)].copy()
        if starters.empty:
            fig = go.Figure()
            fig.update_layout(
                template='gridiron_ink',
                annotations=[dict(text='No WOPR data for selected filters', x=0.5, y=0.5,
                                  showarrow=False, font=dict(size=16, color='#BDE2FF'),
                                  xref='paper', yref='paper')],
            )
            return fig

        fig = px.treemap(
            starters,
            path=['team', 'player'],
            values=size_col,
            color='points',
            color_continuous_scale='RdYlGn',
            template='gridiron_ink',
            hover_data={'points': ':.1f', size_col: ':.3f'},
        )
        fig.update_traces(
            hovertemplate='<b>%{label}</b><br>' + size_col.upper() +
                          ': <b>%{value:.3f}</b><br>Pts: <b>%{color:.1f}</b><extra></extra>',
        )
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        return fig

    def WaiverWireBump(self, top_n=15, mode='rank'):
        """Bump chart: rank or cumulative points of top players over the season."""
        if self.BreakoutSeason is None or self.BreakoutSeason.empty:
            return go.Figure()

        bs = self.BreakoutSeason[self.BreakoutSeason['player'].notna()].copy()

        # Cumulative points per player per week
        bs = bs[bs['week_NFL'].notna()].copy()
        bs['week_NFL'] = bs['week_NFL'].astype(int)
        player_week = bs.groupby(['player', 'week_NFL', 'position'])['points'].sum().reset_index()
        player_week = player_week.sort_values(['player', 'week_NFL'])
        player_week['cumulative'] = player_week.groupby('player')['points'].cumsum()

        # Rank players each week by cumulative points
        player_week['rank'] = player_week.groupby('week_NFL')['cumulative'].rank(
            ascending=False, method='min')

        # Find top_n players by final cumulative score
        final_week = player_week['week_NFL'].max()
        top_players = (
            player_week[player_week['week_NFL'] == final_week]
            .nsmallest(top_n, 'rank')['player'].tolist()
        )

        subset = player_week[player_week['player'].isin(top_players)]

        pos_colors = {
            'QB': '#FFC300', 'RB': '#54A2E5',
            'WR': '#90BE6D', 'TE': '#F94144', 'K': '#9467BD',
        }

        use_points = (mode == 'points')

        fig = go.Figure()
        for player in top_players:
            pdata = subset[subset['player'] == player].sort_values('week_NFL')
            if pdata.empty:
                continue
            pos = pdata['position'].iloc[0]
            color = pos_colors.get(pos, '#BDE2FF')
            y_vals = pdata['cumulative'].values if use_points else pdata['rank'].values
            hover = (
                f'<b>{player}</b> ({pos})<br>'
                'Week %{x}<br>'
                + ('Cumulative Pts: <b>%{y:.1f}</b><extra></extra>' if use_points
                   else 'Rank: <b>%{y:.0f}</b><br>Cumulative Pts: <b>%{customdata:.1f}</b><extra></extra>')
            )
            fig.add_trace(go.Scatter(
                x=pdata['week_NFL'],
                y=y_vals,
                mode='lines+markers',
                name=f'{player} ({pos})',
                line=dict(color=color, width=2, shape='spline'),
                marker=dict(size=6),
                hovertemplate=hover,
                customdata=pdata['cumulative'].values if not use_points else None,
            ))

        if use_points:
            fig.update_yaxes(title='Cumulative Points')
        else:
            fig.update_yaxes(autorange='reversed', title='Rank')
        fig.update_xaxes(title='Week', dtick=1)
        fig.update_layout(
            template='gridiron_ink',
            showlegend=True,
            legend=dict(orientation='v', x=1.01, xanchor='left'),
        )
        return fig

    def LineupEfficiency(self, week):
        """Returns DataFrame: actual vs optimal scores with gap per team."""
        if self.BreakoutSeason is None or self.BreakoutSeason.empty:
            return pd.DataFrame()
        if self.Matches is None or self.Matches.empty:
            return pd.DataFrame()

        week_data = self.BreakoutSeason[
            self.BreakoutSeason['week_NFL'] == float(week)
        ].copy()
        if week_data.empty:
            return pd.DataFrame()

        actuals = (
            self.Matches[self.Matches['Week'] == week]
            .set_index('Team')['Total'].to_dict()
        )
        if not actuals:
            return pd.DataFrame()

        SLOTS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DEF': 1}
        FLEX_POSITIONS = {'RB', 'WR', 'TE'}

        rows = []
        for team, actual in actuals.items():
            team_players = week_data[week_data['team'] == team]
            if team_players.empty:
                continue
            used = set()
            optimal_pts = 0.0
            # Fill positional slots greedily (best player first)
            for pos, count in SLOTS.items():
                best = (
                    team_players[team_players['position'] == pos]
                    .sort_values('points', ascending=False)
                    .head(count)
                )
                for idx in best.index:
                    used.add(idx)
                    optimal_pts += best.loc[idx, 'points']
            # Flex: best remaining RB/WR/TE
            flex_candidates = (
                team_players[
                    team_players['position'].isin(FLEX_POSITIONS) &
                    ~team_players.index.isin(used)
                ].sort_values('points', ascending=False)
            )
            if not flex_candidates.empty:
                best_flex = flex_candidates.iloc[0]
                used.add(flex_candidates.index[0])
                optimal_pts += best_flex['points']

            rows.append({
                'Team': team,
                'Actual': round(actual, 2),
                'Optimal': round(optimal_pts, 2),
                'Gap': round(optimal_pts - actual, 2),
                'Efficiency': actual / optimal_pts if optimal_pts > 0 else 1.0,
            })
        return pd.DataFrame(rows).sort_values('Gap', ascending=False)

    def LineupEfficiencyChart(self, week):
        """Waterfall-style bar chart: actual vs optimal score per team."""
        df = self.LineupEfficiency(week)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(template='gridiron_ink',
                annotations=[dict(text='No efficiency data available', x=0.5, y=0.5,
                    showarrow=False, font=dict(size=16, color='#BDE2FF'), xref='paper', yref='paper')])
            return fig

        fig = go.Figure()

        # Actual score bars
        fig.add_trace(go.Bar(
            name='Actual Score',
            x=df['Team'],
            y=df['Actual'],
            marker_color='#54A2E5',
            marker_line_color='rgba(0,0,0,0.25)',
            marker_line_width=1,
            hovertemplate='<b>%{x}</b><br>Actual: <b>%{y:.1f}</b><extra></extra>',
        ))

        # Gap bars (points left on bench)
        fig.add_trace(go.Bar(
            name='Left on Bench',
            x=df['Team'],
            y=df['Gap'],
            marker_color='rgba(249,65,68,0.6)',
            marker_line_color='rgba(0,0,0,0.25)',
            marker_line_width=1,
            hovertemplate='<b>%{x}</b><br>+%{y:.1f} pts left on bench<extra></extra>',
            text=[f'+{g:.1f}' for g in df['Gap']],
            textposition='outside',
            textfont=dict(color='#F94144', size=11),
        ))

        # Horizontal layout: teams on y-axis, points on x-axis
        fig_h = go.Figure()

        fig_h.add_trace(go.Bar(
            name='Actual Score',
            y=df['Team'],
            x=df['Actual'],
            orientation='h',
            marker_color=[self.teamcolors.get(t, '#54A2E5') for t in df['Team']],
            marker_line_color='rgba(0,0,0,0.25)',
            marker_line_width=1,
            hovertemplate='<b>%{y}</b><br>Actual: <b>%{x:.1f}</b><extra></extra>',
        ))

        _gap_bar_colors = [
            'rgba(249,65,68,0.55)' if g >= 0 else 'rgba(78,205,196,0.55)'
            for g in df['Gap']
        ]
        _gap_texts = [f'<b>+{g:.1f}</b>' if g >= 0 else f'<b>{g:.1f}</b>' for g in df['Gap']]
        _gap_hover = [
            f'<b>{t}</b><br>+{g:.1f} pts left on bench' if g >= 0
            else f'<b>{t}</b><br>Beat optimal by {abs(g):.1f} pts'
            for t, g in zip(df['Team'], df['Gap'])
        ]

        fig_h.add_trace(go.Bar(
            name='Left on Bench',
            y=df['Team'],
            x=df['Gap'],
            orientation='h',
            marker_color=_gap_bar_colors,
            marker_line_color='rgba(0,0,0,0.25)',
            marker_line_width=1,
            hovertext=_gap_hover,
            hovertemplate='%{hovertext}<extra></extra>',
            text=_gap_texts,
            textposition='outside',
            textfont=dict(color=['#F94144' if g >= 0 else '#4ECDC4' for g in df['Gap']], size=11),
        ))

        fig_h.update_layout(
            template='gridiron_ink',
            barmode='stack',
            showlegend=True,
            xaxis_title='Points',
            yaxis_title=None,
            legend=dict(orientation='h', x=0.5, xanchor='center', y=1.05),
            yaxis=dict(
                autorange='reversed',
                showticklabels=False,
            ),
        )
        # Colored team name labels via annotations (Plotly doesn't support per-tick colors)
        for team in df['Team']:
            color = self.teamcolors.get(team, '#BDE2FF')
            fig_h.add_annotation(
                x=0, y=team,
                xref='paper', yref='y',
                text=f'<b>{team}</b>',
                showarrow=False,
                font=dict(color=color, size=13, family='Courier New'),
                xanchor='right',
                xshift=-6,
                align='right',
            )
        return fig_h


class Playoffs:
    """
    Resolves winners and losers bracket data for a single season into structured
    round-by-round matchup dicts, joined with scores and player stats.

    Usage:
        playoffs = Playoffs(league, season)
        playoffs.winners   # {1: [...], 2: [...], 3: [...]}
        playoffs.losers    # same structure, no player stats
    """

    def __init__(self, league, season):
        import data_loader as dl

        self.league = league
        self.year = league.year
        self.playoff_week_start = int(
            league.league_settings.get('settings.playoff_week_start', 15)
        )
        self._roster_map = {int(k): v for k, v in roster_ids[self.year].items()}

        winners_raw = dl.fetch_winners_bracket(league.id)
        losers_raw  = dl.fetch_losers_bracket(league.id)

        self.winners = self._process_bracket(winners_raw, include_stats=True)
        self.losers  = self._process_bracket(losers_raw,  include_stats=False)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _team_name(self, roster_id):
        return self._roster_map.get(int(roster_id), f"Roster {roster_id}")

    def _week_frames(self, round_num):
        week = self.playoff_week_start + round_num - 1
        matches  = AllMatchesDict.get(self.year, {}).get(week, pd.DataFrame())
        breakout = AllBreakoutDict.get(self.year, {}).get(week, pd.DataFrame())
        return matches, breakout

    def _score(self, matches_df, team_name):
        if matches_df.empty:
            return 0.0
        row = matches_df[matches_df['Team'] == team_name]
        return float(row['Total'].iloc[0]) if not row.empty else 0.0

    def _best_player(self, breakout_df, team1, team2):
        if breakout_df.empty:
            return 'N/A'
        starters = breakout_df[
            (breakout_df['team'].isin([team1, team2])) & (breakout_df['starter'] == 1)
        ]
        if starters.empty:
            return 'N/A'
        best = starters.loc[starters['points'].idxmax()]
        return f"{best['player']} ({best['points']:.1f})"

    def _bench_left(self, breakout_df, team_name):
        """Total points scored by bench players for a team that week."""
        if breakout_df.empty:
            return 0.0
        bench = breakout_df[
            (breakout_df['team'] == team_name) & (breakout_df['starter'] == 0)
        ]
        return float(bench['points'].sum()) if not bench.empty else 0.0

    def _efficiency(self, round_num, team_name, actual_score):
        """Lineup efficiency: actual / optimal * 100. Returns None if unavailable."""
        week = self.playoff_week_start + round_num - 1
        opt_df = OptimalScoresByYear.get(self.year, {}).get(week)
        if opt_df is None or opt_df.empty or actual_score == 0:
            return None
        row = opt_df[opt_df['team'] == team_name]
        if row.empty:
            return None
        optimal = float(row['points'].sum())
        return round(actual_score / optimal * 100, 1) if optimal > 0 else None

    # ── Core processing ───────────────────────────────────────────────────────

    def _process_bracket(self, bracket_raw, include_stats):
        by_round = {}
        for entry in bracket_raw:
            by_round.setdefault(entry['r'], []).append(entry)

        rounds = {}
        for round_num, entries in by_round.items():
            matches_df, breakout_df = self._week_frames(round_num)
            matchups = []

            for entry in entries:
                t1_id = entry.get('t1')
                t2_id = entry.get('t2')
                if t1_id is None or t2_id is None:
                    continue  # bracket not yet resolved (in-progress season)

                team1  = self._team_name(t1_id)
                team2  = self._team_name(t2_id)
                w_id   = entry.get('w')
                winner = self._team_name(w_id) if w_id is not None else None

                score1 = self._score(matches_df, team1)
                score2 = self._score(matches_df, team2)

                matchup = {
                    'match':       entry['m'],
                    'team1':       team1,
                    'score1':      score1,
                    'team2':       team2,
                    'score2':      score2,
                    'winner':      winner,
                    'placement':   entry.get('p'),
                    'efficiency1': self._efficiency(round_num, team1, score1),
                    'efficiency2': self._efficiency(round_num, team2, score2),
                }

                if include_stats:
                    matchup['best_player'] = self._best_player(breakout_df, team1, team2)
                    matchup['bench_left']  = (
                        self._bench_left(breakout_df, winner) if winner else 0.0
                    )

                matchups.append(matchup)

            # Main bracket games (no placement) sort before placement games
            matchups.sort(key=lambda m: (m['placement'] is not None, m['placement'] or 0, m['match']))
            rounds[round_num] = matchups

        return rounds

    # ── Analytics charts ──────────────────────────────────────────────────────

    def ChampionRoad(self):
        """Horizontal grouped bar: champion's score vs opponent each round."""
        champ_match = next((m for m in self.winners.get(3, []) if m.get('placement') == 1), None)
        if not champ_match:
            return go.Figure()
        champion = champ_match['winner']

        ROUND_LABELS = {1: 'Wild Card', 2: 'Semifinals', 3: 'Championship'}
        rounds_data = []
        for rnd in sorted(self.winners):
            for m in self.winners[rnd]:
                if champion not in (m['team1'], m['team2']):
                    continue
                is_t1 = champion == m['team1']
                rounds_data.append({
                    'label':       f"{ROUND_LABELS.get(rnd, f'Round {rnd}')} · Wk {self.playoff_week_start + rnd - 1}",
                    'champ_score': m['score1'] if is_t1 else m['score2'],
                    'opp_score':   m['score2'] if is_t1 else m['score1'],
                    'opponent':    m['team2']  if is_t1 else m['team1'],
                })

        labels      = [d['label']       for d in rounds_data]
        champ_scores= [d['champ_score'] for d in rounds_data]
        opp_scores  = [d['opp_score']   for d in rounds_data]
        opponents   = [d['opponent']    for d in rounds_data]

        fig = go.Figure([
            go.Bar(name=champion,   y=labels, x=champ_scores, orientation='h',
                   marker_color='#FFC300',
                   text=[f"{s:.1f}" for s in champ_scores], textposition='outside'),
            go.Bar(name='Opponent', y=labels, x=opp_scores,   orientation='h',
                   marker_color='#3D5E78',
                   text=[f"{s:.1f} ({o})" for s, o in zip(opp_scores, opponents)],
                   textposition='outside'),
        ])
        fig.update_layout(template='gridiron_ink', barmode='group',
                          title=None, xaxis_title='Points', height=320,
                          margin=dict(t=20, b=40, l=160, r=120))
        return fig

    def PlayoffHeatCheck(self):
        """Grouped bar: each playoff team's last-3-regular-season-week avg vs playoff avg."""
        playoff_teams = sorted({
            m[t] for rnd in self.winners.values() for m in rnd for t in ('team1', 'team2')
        })
        reg_end   = self.playoff_week_start - 1
        reg_weeks = list(range(max(1, reg_end - 2), reg_end + 1))   # last 3 regular weeks
        pl_weeks  = list(range(self.playoff_week_start, self.playoff_week_start + 3))

        def avg(team, weeks):
            scores = []
            for wk in weeks:
                df = AllMatchesDict.get(self.year, {}).get(wk, pd.DataFrame())
                if df.empty:
                    continue
                row = df[df['Team'] == team]
                if not row.empty:
                    scores.append(float(row['Total'].iloc[0]))
            return round(sum(scores) / len(scores), 2) if scores else 0.0

        reg_avgs = [avg(t, reg_weeks) for t in playoff_teams]
        pl_avgs  = [avg(t, pl_weeks)  for t in playoff_teams]

        fig = go.Figure([
            go.Bar(name=f'Wks {reg_weeks[0]}–{reg_weeks[-1]} Avg', x=playoff_teams, y=reg_avgs,
                   marker_color='#3D5E78',
                   text=[f"{v:.1f}" for v in reg_avgs], textposition='outside'),
            go.Bar(name='Playoff Avg', x=playoff_teams, y=pl_avgs,
                   marker_color='#FFC300',
                   text=[f"{v:.1f}" for v in pl_avgs], textposition='outside'),
        ])
        fig.update_layout(template='gridiron_ink', barmode='group',
                          title=None, yaxis_title='Avg Points', height=420,
                          margin=dict(t=20, b=80, l=60, r=40))
        return fig

    def BenchPointsLeft(self):
        """Grouped bar: bench points left per team per winners-bracket game."""
        ROUND_SHORT = {1: 'WC', 2: 'Semi', 3: 'Final'}
        labels, t1_vals, t2_vals, t1_names, t2_names = [], [], [], [], []

        for rnd in sorted(self.winners):
            week     = self.playoff_week_start + rnd - 1
            breakout = AllBreakoutDict.get(self.year, {}).get(week, pd.DataFrame())
            for m in self.winners[rnd]:
                lbl = f"{ROUND_SHORT.get(rnd, f'R{rnd}')} · {m['team1'][:9]} vs {m['team2'][:9]}"
                labels.append(lbl)
                t1_vals.append(self._bench_left(breakout, m['team1']))
                t2_vals.append(self._bench_left(breakout, m['team2']))
                t1_names.append(m['team1'])
                t2_names.append(m['team2'])

        fig = go.Figure([
            go.Bar(y=labels, x=t1_vals, name='Team 1', orientation='h',
                   marker_color='#4A90D9',
                   text=[f"{v:.1f}" for v in t1_vals], textposition='outside',
                   customdata=t1_names,
                   hovertemplate='%{customdata}: %{x:.1f} pts<extra></extra>'),
            go.Bar(y=labels, x=t2_vals, name='Team 2', orientation='h',
                   marker_color='#E8A838',
                   text=[f"{v:.1f}" for v in t2_vals], textposition='outside',
                   customdata=t2_names,
                   hovertemplate='%{customdata}: %{x:.1f} pts<extra></extra>'),
        ])
        fig.update_layout(template='gridiron_ink', barmode='group',
                          title=None, xaxis_title='Points on Bench', height=420,
                          margin=dict(t=20, b=40, l=290, r=80))
        return fig


class AllTimePlayoffs:
    """
    Aggregates winners-bracket playoff data across all available seasons.

    Attributes:
        playoff_results  — one row per team per year they made the playoffs
        playoff_games    — one row per team per playoff game (both brackets)
    """

    def __init__(self):
        import data_loader as dl
        self._build(dl)

    # ── Data helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_score(matches_df, team_name):
        if matches_df.empty:
            return 0.0
        row = matches_df[matches_df['Team'] == team_name]
        return float(row['Total'].iloc[0]) if not row.empty else 0.0

    def _process_year(self, year, league_id, dl, results_rows, games_rows):
        league_json = dl.fetch_league_json(league_id)
        playoff_week_start = int(
            league_json.get('settings', {}).get('playoff_week_start', 15)
        )
        roster_map = {int(k): v for k, v in roster_ids[year].items()}

        # Regular season standings (wins → PF tiebreaker)
        reg_weeks_data = {wk: df for wk, df in AllMatchesDict.get(year, {}).items()
                          if wk < playoff_week_start and not df.empty}
        if not reg_weeks_data:
            return

        all_reg = pd.concat(list(reg_weeks_data.values()), ignore_index=True)
        rec = all_reg.groupby('Team').agg(wins=('Won', 'sum'), total_pf=('Total', 'sum'))
        standings_order = sorted(
            rec.index,
            key=lambda t: (-rec.loc[t, 'wins'], -rec.loc[t, 'total_pf'])
        )
        reg_rank = {t: i + 1 for i, t in enumerate(standings_order)}

        winners_raw = dl.fetch_winners_bracket(league_id)
        losers_raw  = dl.fetch_losers_bracket(league_id)

        # Process both brackets into flat game rows
        year_games = []
        for bracket_raw, bracket_name in [(winners_raw, 'winners'), (losers_raw, 'losers')]:
            by_round = {}
            for entry in bracket_raw:
                by_round.setdefault(entry['r'], []).append(entry)

            for rnd, entries in sorted(by_round.items()):
                week = playoff_week_start + rnd - 1
                matches_df = AllMatchesDict.get(year, {}).get(week, pd.DataFrame())

                for entry in entries:
                    t1_id = entry.get('t1')
                    t2_id = entry.get('t2')
                    if t1_id is None or t2_id is None:
                        continue  # in-progress / unresolved

                    team1 = roster_map.get(int(t1_id), f"Roster {t1_id}")
                    team2 = roster_map.get(int(t2_id), f"Roster {t2_id}")
                    w_id  = entry.get('w')
                    winner = roster_map.get(int(w_id)) if w_id else None
                    is_placement = entry.get('p') is not None

                    score1 = self._get_score(matches_df, team1)
                    score2 = self._get_score(matches_df, team2)

                    for team, score, opp, opp_score in [
                        (team1, score1, team2, score2),
                        (team2, score2, team1, score1),
                    ]:
                        year_games.append({
                            'year': year, 'week': week, 'round': rnd,
                            'match_id': entry['m'],
                            'team': team, 'score': score,
                            'opponent': opp, 'opp_score': opp_score,
                            'won': winner == team,
                            'bracket': bracket_name,
                            'placement_game': is_placement,
                        })

        games_rows.extend(year_games)

        # Collect all winners-bracket participants
        winners_teams = set()
        for entry in winners_raw:
            for key in ('t1', 't2'):
                rid = entry.get(key)
                if rid is not None:
                    winners_teams.add(roster_map.get(int(rid), str(rid)))

        # Placement from placement-game entries (p=1 → 1st/2nd, p=3 → 3rd/4th, p=5 → 5th/6th)
        placement_map = {}
        for entry in winners_raw:
            p   = entry.get('p')
            w_id = entry.get('w')
            l_id = entry.get('l')
            if p is not None and w_id and l_id:
                placement_map[roster_map.get(int(w_id))] = p
                placement_map[roster_map.get(int(l_id))] = p + 1

        # Per-team stats from this year's winners games
        winner_year_games = [g for g in year_games if g['bracket'] == 'winners']
        team_stats = {}
        for g in winner_year_games:
            t = g['team']
            if t not in team_stats:
                team_stats[t] = {'wins': 0, 'losses': 0, 'rounds': set()}
            team_stats[t]['rounds'].add(g['round'])
            if g['won']:
                team_stats[t]['wins'] += 1
            elif not g['placement_game']:
                team_stats[t]['losses'] += 1

        for team in winners_teams:
            s = team_stats.get(team, {'wins': 0, 'losses': 0, 'rounds': set()})
            results_rows.append({
                'year': year,
                'team': team,
                'reg_season_rank': reg_rank.get(team, 999),
                'round_exit': max(s['rounds']) if s.get('rounds') else 0,
                'placement': placement_map.get(team),
                'wins': s['wins'],
                'losses': s['losses'],
            })

    def _build(self, dl):
        results_rows, games_rows = [], []
        for year in AVAILABLE_YEARS:
            league_id = leagueNumbers_Dict.get(year)
            if not league_id:
                continue
            try:
                self._process_year(year, league_id, dl, results_rows, games_rows)
            except Exception as e:
                print(f"[AllTimePlayoffs] Skipping {year}: {e}")

        _empty_results = pd.DataFrame(columns=[
            'year', 'team', 'reg_season_rank', 'round_exit', 'placement', 'wins', 'losses'])
        _empty_games = pd.DataFrame(columns=[
            'year', 'week', 'round', 'match_id', 'team', 'score',
            'opponent', 'opp_score', 'won', 'bracket', 'placement_game'])

        self.playoff_results = pd.DataFrame(results_rows) if results_rows else _empty_results
        self.playoff_games   = pd.DataFrame(games_rows)   if games_rows   else _empty_games

    # ── 6B: Playoff Pedigree ──────────────────────────────────────────────────

    def PlayoffPedigree(self):
        """Horizontal overlay bar: appearances / semis / finals / championships."""
        if self.playoff_results.empty:
            return go.Figure()

        df = self.playoff_results.copy()
        teams_ordered = (df.groupby('team').size()
                           .sort_values(ascending=True).index.tolist())

        rows = []
        for team in teams_ordered:
            t = df[df['team'] == team]
            rows.append({
                'team': team,
                'appearances': len(t),
                'semis':  int((t['round_exit'] >= 2).sum()),
                'finals': int((t['round_exit'] >= 3).sum()),
                'champs': int((t['placement'] == 1).sum()),
            })
        stats = pd.DataFrame(rows)

        fig = go.Figure([
            go.Bar(name='Appearances',   y=stats['team'], x=stats['appearances'],
                   orientation='h', marker_color='rgba(61,94,120,0.9)',   width=0.6),
            go.Bar(name='Semifinals+',   y=stats['team'], x=stats['semis'],
                   orientation='h', marker_color='rgba(84,162,229,0.85)', width=0.45),
            go.Bar(name='Finals',        y=stats['team'], x=stats['finals'],
                   orientation='h', marker_color='rgba(189,226,255,0.9)', width=0.3),
            go.Bar(name='Championships', y=stats['team'], x=stats['champs'],
                   orientation='h', marker_color='#FFC300',               width=0.15),
        ])
        fig.update_layout(
            template='gridiron_ink', barmode='overlay',
            height=420, margin=dict(t=20, b=20, l=150, r=60),
            xaxis=dict(title='Count', dtick=1,
                       range=[0, stats['appearances'].max() + 0.8]),
            legend=dict(orientation='h', y=-0.08, x=0.5, xanchor='center'),
        )
        return fig

    # ── 6C: Playoff Win Rate ──────────────────────────────────────────────────

    def PlayoffWinRate(self):
        """Horizontal bar: playoff win rate per manager (competitive rounds only)."""
        if self.playoff_games.empty:
            return go.Figure()

        comp = self.playoff_games[
            (self.playoff_games['bracket'] == 'winners') &
            (~self.playoff_games['placement_game'])
        ].copy()

        stats = comp.groupby('team').agg(wins=('won', 'sum'), games=('won', 'count'))
        stats = stats[stats['games'] >= 2].copy()
        stats['rate']  = stats['wins'] / stats['games']
        stats['label'] = stats.apply(
            lambda r: f"{int(r['wins'])}-{int(r['games'] - r['wins'])}", axis=1)
        stats = stats.sort_values('rate', ascending=True)

        colors = ['#90BE6D' if r >= 0.60 else '#E6DB74' if r >= 0.40 else '#F94144'
                  for r in stats['rate']]

        fig = go.Figure(go.Bar(
            y=stats.index, x=stats['rate'], orientation='h',
            marker_color=colors,
            text=stats['label'], textposition='outside',
        ))
        fig.update_layout(
            template='gridiron_ink',
            height=380, margin=dict(t=20, b=40, l=150, r=90),
            xaxis=dict(title='Win Rate', tickformat='.0%', range=[0, 1.2]),
        )
        return fig

    # ── 6D: Seeding Scatter ───────────────────────────────────────────────────

    def SeedingScatter(self):
        """Scatter: regular season rank vs. playoff finish, all seasons."""
        df = self.playoff_results.dropna(subset=['placement']).copy()
        if df.empty:
            return go.Figure()

        at_colors = get_alltime_teamcolors()
        fig = go.Figure()

        # Reference diagonal — finishing exactly where seeded
        fig.add_trace(go.Scatter(
            x=[1, 6], y=[1, 6], mode='lines',
            line=dict(color='rgba(61,94,120,0.5)', dash='dash', width=1),
            showlegend=False, hoverinfo='skip',
        ))

        for team in sorted(df['team'].unique()):
            t = df[df['team'] == team]
            color = at_colors.get(team, '#BDE2FF')
            fig.add_trace(go.Scatter(
                x=t['reg_season_rank'], y=t['placement'],
                mode='markers+text',
                name=team,
                marker=dict(color=color, size=11,
                             line=dict(width=1, color='rgba(0,0,0,0.3)')),
                text=t['year'].astype(str).str[-2:],
                textposition='top center',
                textfont=dict(size=8, color=color),
                customdata=t['year'],
                hovertemplate=(f'<b>{team}</b><br>Year: %{{customdata}}<br>'
                               f'Reg rank: %{{x}}<br>Playoff finish: %{{y}}<extra></extra>'),
            ))

        fig.update_layout(
            template='gridiron_ink',
            height=480, margin=dict(t=20, b=60, l=60, r=40),
            xaxis=dict(title='Regular Season Rank', dtick=1,
                       range=[0.5, 12.5], autorange=False),
            yaxis=dict(title='Playoff Finish (1 = Champion)', dtick=1,
                       range=[6.8, 0.2], autorange=False),
            legend=dict(orientation='h', y=-0.16, x=0.5, xanchor='center'),
        )
        return fig

    # ── 6F: Path to Glory ────────────────────────────────────────────────────

    def PathToGlory(self):
        """Line chart: each champion's scores across their three playoff rounds."""
        if self.playoff_results.empty or self.playoff_games.empty:
            return go.Figure()

        champs = (self.playoff_results[self.playoff_results['placement'] == 1]
                  .set_index('year')['team'])
        if champs.empty:
            return go.Figure()

        at_colors = get_alltime_teamcolors()
        ROUND_LABELS = {1: 'Wild Card', 2: 'Semifinals', 3: 'Championship'}
        w_games = self.playoff_games[self.playoff_games['bracket'] == 'winners']

        fig = go.Figure()
        for year in sorted(champs.index):
            champion = champs[year]
            color    = at_colors.get(champion, '#BDE2FF')

            games = (w_games[(w_games['year'] == year) & (w_games['team'] == champion)]
                     .sort_values('round'))
            if games.empty:
                continue

            rounds       = [ROUND_LABELS.get(r, f'R{r}') for r in games['round']]
            champ_scores = games['score'].tolist()
            opp_scores   = games['opp_score'].tolist()
            opponents    = games['opponent'].tolist()

            fig.add_trace(go.Scatter(
                x=rounds, y=champ_scores,
                mode='lines+markers',
                name=f'{champion} ({year})',
                line=dict(color=color, width=2),
                marker=dict(color=color, size=9),
                customdata=list(zip([year]*len(rounds), opponents, opp_scores)),
                hovertemplate=(
                    f'<b>{champion} {year}</b><br>%{{x}}: %{{y:.1f}} pts'
                    '<br>vs %{customdata[1]} (%{customdata[2]:.1f})<extra></extra>'
                ),
            ))

        fig.update_layout(
            template='gridiron_ink',
            height=440, margin=dict(t=20, b=80, l=60, r=40),
            xaxis=dict(title='Playoff Round',
                       categoryorder='array',
                       categoryarray=['Wild Card', 'Semifinals', 'Championship']),
            yaxis=dict(title='Points Scored'),
            legend=dict(orientation='h', y=-0.2, x=0.5, xanchor='center'),
        )
        return fig


class AllTime:
    def __init__(self):
               
        self.MatchProcessing()
        self.SetTeamColors()
        self.BreakoutProcessing()
      
        
            
    def Update(self):
        
        self.MatchProcessing()
        
        self.BreakoutProcessing()
        
    def MatchProcessing(self):    
        
        Match_dfs = [df for week_dict in AllMatchesDict.values() for df in week_dict.values()]
           
        self.Matches =  pd.concat(Match_dfs, ignore_index=True)
        
        self.Matches['Abs Margin'] = abs(self.Matches['Margin'].astype(float)).round(2)
        self.Matches['Margin'] = round(self.Matches['Margin'],2) 
        
    def BreakoutProcessing(self):
        
        breakout_dfs = [df for week_dict in AllBreakoutDict.values() for df in week_dict.values()]
    
        self.Breakout =  pd.concat(breakout_dfs, ignore_index=True)
        
        self.Breakout_Playoffs = self.Breakout[self.Breakout.Season == 'Playoff']
        self.Breakout_Regular = self.Breakout[self.Breakout.Season == 'Regular']
    
    def SetTeamColors(self, color_dict:dict = None):
        self.teamcolors = get_alltime_teamcolors()
        if color_dict is not None:
            self.teamcolors = color_dict

    
    def OppWinPercentage(self, team, opp):
        OppTable = pd.pivot_table(self.Matches, values='Won',index='Team',columns='Opp_team',aggfunc='mean').round(2).fillna('')
        result = OppTable.loc[team,opp]
        return result
    
    def OppWinPercentageTable(self):
        all_teams = list(roster_ids_2025.values())
        result = pd.pivot_table(self.Matches, values='Won',index='Team',columns='Opp_team',aggfunc='mean').round(2).fillna('')
        result = result[result.columns.intersection(roster_ids_2025.values())].reset_index()
        result = result[result['Team'].isin(roster_ids_2025.values())].set_index('Team')
        result = result.reindex(index=all_teams, columns=all_teams)
        result = result.fillna(0.50)
        
        # result = result.astype(object)
        # np.fill_diagonal(result.values, '')
        self.OppWinPercentage = result
        #result = result.round(2)
        return result
    
    def TopPlayerScoresProcessing(self):
        
        self.TopTeamScores = self.Matches.sort_values('Total', ascending=False)[:10]
        self.TopTeamScores['Names'] = self.TopTeamScores.Team + ' [W' + self.TopTeamScores.Week.astype(str) + ' ' + self.TopTeamScores.Year.astype(str)+ ']' + ' - ' + self.TopTeamScores.Total.round(1).astype(str) 
        self.TopTeamScores['Year'] = self.TopTeamScores['Year'].astype(int)
        
        self.BottomTeamScores = self.Matches.sort_values('Total', ascending=True)[:10]
        self.BottomTeamScores['Names'] = self.BottomTeamScores.Team + ' [W' + self.BottomTeamScores.Week.astype(str) + ' ' + self.BottomTeamScores.Year.astype(str)+ ']' + ' - ' + self.BottomTeamScores.Total.round(1).astype(str) 
        self.BottomTeamScores['Year'] = self.BottomTeamScores['Year'].astype(int)
        
        self.TopPlayerScores = self.Breakout.sort_values('points', ascending=False)[:10].rename(columns={'team': 'Team'})
        self.TopPlayerScores['Names'] = self.TopPlayerScores.Team + ' [W' + self.TopPlayerScores.week_x.astype(str) + ' ' + self.TopPlayerScores.year.astype(str)+ ']' + ' - ' + self.TopPlayerScores.points.round(1).astype(str)
        self.TopPlayerScores['Year'] = self.TopPlayerScores['year'].astype(int)

        self.BottomPlayerScores = self.Breakout.sort_values('points', ascending=True)[:10].rename(columns={'team': 'Team'})
        self.BottomPlayerScores['Names'] = self.BottomPlayerScores.Team + ' [W' + self.BottomPlayerScores.week_x.astype(str) + ' ' + self.BottomPlayerScores.year.astype(str)+ ']' + ' - ' + self.BottomPlayerScores.points.round(1).astype(str)
        self.BottomPlayerScores['Year'] = self.BottomPlayerScores['year'].astype(int)

    
    ### GRAPHS
    
    def TopScores(self, Top_Bottom = 'Top', Team_Player = 'Team'):
        
        self.TopPlayerScoresProcessing()

        if Top_Bottom == 'Top' and Team_Player == 'Team':
            dfgraph = self.TopTeamScores
            Title = '<b>Hall of Fame</b><br><sup>Team</sup>'
            x_graph = 'Total'
            
        elif Top_Bottom == 'Bottom' and Team_Player == 'Team':
            dfgraph = self.BottomTeamScores
            Title = '<b>Hall of Shame</b><br><sup>Players</sup>'
            x_graph = "Total"
            
            
        elif Top_Bottom == 'Top' and Team_Player == 'Player':
            dfgraph = self.TopPlayerScores
            Title = "<b>Hall of Fame</b><br><sup>Player</sup>"
            x_graph = 'points'
        
        elif Top_Bottom == 'Bottom' and Team_Player == 'Player':
            dfgraph = self.BottomPlayerScores
            Title = "<b>Hall of Shame</b><br><sup>Player</sup>"
            x_graph = 'points'
            
        
            
        figTopScores = px.bar(dfgraph , y='Names', x=x_graph, template = 'gridiron_ink',
                             color = 'Team', orientation='h', text = 'Names', title =Title,)
                             
                             
                             
        figTopScores.update_layout(height = 1200, width = 900)
        figTopScores.update_layout(yaxis={'categoryorder': 'total ascending'})
        if Top_Bottom == 'Bottom':
            figTopScores.update_layout(yaxis = {'categoryorder':'total descending'})
        figTopScores.update_coloraxes(showscale=False)
        figTopScores.update_layout(title_font = dict(size=40),xaxis=dict(title=dict(text="")))   
        figTopScores.update_layout(
            font=dict(
                size=18,  # Set the font size here
            )
        )
        figTopScores.update_layout(margin=dict(t=130, b=100, l=40, r=40))
        figTopScores.update_layout(yaxis={'visible': False, 'showticklabels': False})
        apply_logo_to_fig(figTopScores)
        
        

        return figTopScores


    def AllTimeGraphing(self,df,week):
        df = pd.concat(AllMatches).sort_values('Week Index')
        fig2 = px.line(df,x='Week Index',y='Total Wins', color = 'Team',template='gridiron_ink',line_shape = 'spline', title = 'All-Time Wins')
        fig2.update_xaxes(
                        tickfont=dict(
                family='Courier New',  # Font family
                size=18,         # Font size
                color='white'    # Font color
            ))
        fig2.update_yaxes(dtick=10)
        fig2.update_layout(width=1400, height=900)
        # Adjust the thickness of the lines
        fig2.update_traces(line=dict(width=4))  # Set the line width (e.g., 3 pixels)
        fig2.update_layout(legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title = ''
        ))

        #fig2.update_layout(showlegend = False)
        # Customize the y-axis labels
        fig2.update_yaxes(
            tickfont=dict(
                size=20,         # Font size
            )
        )

        fig2.update_layout(uniformtext_minsize=10, uniformtext_mode='hide')

        # Update x-axis and y-axis titles with font customization
        fig2.update_layout(
            xaxis_title="Week",  # Set x-axis title
            yaxis_title="Wins",   # Set y-axis title
            xaxis=dict(dtick = 10,
                title_font=dict(
                    size=20          # Set font size for x-axis title
                )
            ),
            yaxis=dict(
                title_font=dict(
                    size=20          # Set font size for y-axis title
                )
            )
        )
        
        # Determine final wins and sort by them
        final_scores = [(d.name, d.x[-1], d.y[-1], d.line.color) for d in fig2.data]
        final_scores.sort(key=lambda x: -x[2])  # Sort by final win count, descending

        # Define a list of potential text positions to avoid overlap
        text_positions = ['middle right','top right', 'bottom right', 'top left', 'bottom left', 'middle left']

        previous_score = None
        position_index = 0
        '''
        for team_name, x_final, y_final, color in final_scores:
            if y_final == previous_score:
                # Cycle through text positions to avoid overlap if scores are the same
                position_index = (position_index + 1) % len(text_positions)
            else:
                position_index = 0  # Reset position index when score changes

            text_position = text_positions[position_index]
            previous_score = y_final

            fig2.add_scatter(
                x=[x_final], y=[y_final],
                mode='markers+text',
                text=[team_name],
                textfont=dict(family="Courier New",color=color, size=14, weight = 'bold'),
                textposition=text_position,
                marker=dict(color=color, size=12),
                showlegend=False
                )    
            fig2.update_layout(
            margin=dict(l=50, r=100, t=50, b=50)  # Set left, right, top, bottom padding within the plot area
                )
            
            '''
        fig2.update_layout(xaxis=dict(range=[0, week + 3])) 
        fig2.update_layout(title=dict(
                font=dict(
                    size=50,
                    family="Courier New"))) 
        
        # Find the last data point for each host
        last_points = AllMatches.groupby('Team').apply(lambda d: d.nlargest(1, 'Total Wins','last')).reset_index(drop=True)

        # Define the subset of hosts to style differently
        special_hosts = ['SleeperGawd69']
        special_hosts2 = ['sgmaddox', 'RReclam', 'BillyRayGonnaGetcha','jhuntmadd']
        special_hosts3 = ['eegrady', 'Just_Here_For_The_Snacks']
        special_hosts4 = []
        special_hosts5 = ['GurlyGirls', 'SweetDizzzzzle', 'YouthPastor']
        normal_teams = ['bgmaddox', 'jlglover', 'BMoreBallers88', 'RascalHazard', 'InfiniteJess', 'DirtyCommie', 'JTizzzzle', 'RossLikeSauce','akbrown29']

        for i, row in last_points.iterrows():
            if row['Team'] in special_hosts:
                # Apply special styling for the subset
                text_position = 'top left'
                marker_size = 12
                text_color = 'lightgrey'
                # Default offset
                x_offset = -20
                y_offset = -50
                show_arrow = True
            elif row['Team'] in special_hosts2:
                x_offset = 30
                y_offset = 25
                text_position = 'top left'
                marker_size = 12
                text_color = 'lightgrey'
                show_arrow = True
            elif row['Team'] in special_hosts3:
                x_offset = 50
                y_offset = -20
                text_position = 'top left'
                marker_size = 12
                text_color = 'lightgrey'
                show_arrow = True    
            elif row['Team'] in special_hosts4:
                x_offset = -75
                y_offset = -75
                text_position = 'middle right'
                marker_size = 12
                text_color = 'lightgrey'
                show_arrow = True   
            elif row['Team'] in special_hosts5:
                x_offset = -75
                y_offset = -75
                text_position = 'middle right'
                marker_size = 12
                text_color = 'lightgrey'
                show_arrow = True   
            elif row['Team'] in normal_teams:
                x_offset = 75
                y_offset = 0
                text_position = 'middle right'
                marker_size = 12
                text_color = 'lightgrey'
                show_arrow = True   
            else:
                # Default styling
                text_position = 'top right'
                marker_size = 12
                #text_color = 'lightgrey'
                # Default offset
                x_offset = -100
                y_offset = -0
                show_arrow = False
            fig2.add_annotation(
                x=row['Week Index'],
                y=row['Total Wins'],
                text=row['Team'],
                showarrow=show_arrow,
                arrowhead=2,
                ax=x_offset,
                ay=y_offset,
                font=dict(
                    size=18,
                    #color="white",
                    weight = 'bold'
                ),
                align="left"
            )
        fig2.update_layout(legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-.30,
            xanchor="center",
            x=.5,
            title = '',
            font_size=18,
        ))
        return fig2
    
    
    def HighestScoringLosers(self, team_colors = None):
        
        Losers = self.Matches[(self.Matches['Won'] == 0) & self.Matches['Opp'].notna() & (self.Matches['Opp'] > 0) & self.Matches['Opp_team'].notna()]
        TopTenLosers = Losers.sort_values('Total', ascending=False).head(10)
        TopTenLosers['TeamName'] = "<b>" + TopTenLosers['Team'] + '</b><br>' + "W" +TopTenLosers['Week'].astype(str) + " " + TopTenLosers['Year'].astype(str)
        TopTenLosers['Opp'] = round(TopTenLosers['Opp'],2)
        TopTenLosers['OppName'] = TopTenLosers['Opp_team'] + ' - ' + TopTenLosers['Opp'].astype(str)
        TopTenLosers = TopTenLosers.sort_values('Total')
        
        figLosers = go.Figure()
        figLosers.add_trace(go.Bar(
            x = TopTenLosers['Total'],
            y = TopTenLosers['TeamName'],
            name = 'Losers',
            orientation='h',
            text = TopTenLosers['Total'],
            textfont=dict(size=25),
            marker_color=[self.teamcolors.get(t, '#BDE2FF') for t in TopTenLosers['Team']],
        ))
        figLosers.add_trace(go.Bar(
            x = TopTenLosers['Opp'],
            y = TopTenLosers['TeamName'],
            name = 'Winners',
            orientation='h',
            opacity=.7,
            text = TopTenLosers['OppName'],
            textfont=dict(size=14),
            marker_color=[self.teamcolors.get(t, '#BDE2FF') for t in TopTenLosers['Opp_team']],
            ))
        figLosers.update_layout(template="gridiron_ink", barmode='group')
        figLosers.update_layout(width=800, height=1200)
        figLosers.update_layout(showlegend=False)
        figLosers.update_yaxes(showticklabels=False, title=None)
        for label, team in zip(TopTenLosers['TeamName'], TopTenLosers['Team']):
            figLosers.add_annotation(
                x=0, y=label, xref='paper', yref='y',
                text=label, showarrow=False,
                xanchor='right', align='right', xshift=-8,
                font=dict(color=self.teamcolors.get(team, '#BDE2FF'), size=16, family='Courier New'),
            )
        figLosers.update_layout(
            title = "<b>Biggest Losers</b><br><sup>Highest Scores in Loss</sup>",
        )
        figLosers.update_layout(margin=MARGIN_HBAR)
        apply_logo_to_fig(figLosers, xval=.35)


        return figLosers
        
    def SmallestMargins(self):
        TenSmallestMargins = self.Matches.sort_values('Abs Margin', ascending=True)[:20]
        TenSmallestMargins = TenSmallestMargins.sort_values('Margin').reset_index()
        TenSmallestMargins['TeamGraph'] = TenSmallestMargins['Team'] + ' - ' + TenSmallestMargins['Year'].astype(str) + ' [' + TenSmallestMargins['Margin'].astype(str) + ']'
        
    
        figMargin = px.bar(TenSmallestMargins, x='Margin',y=TenSmallestMargins.index,template = 'gridiron_ink',title='<b>Top 10 Smallest Margins</b>', color = 'Team', orientation='h', text='TeamGraph', color_discrete_map=self.teamcolors)
        figMargin.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'})
        figMargin.update_layout(width=None, height=800)

        figMargin.update_traces(textfont_size=20, textangle=0, cliponaxis=True, textposition = 'auto', textfont=dict(weight='bold', size=15))
        figMargin.update_layout(
                xaxis_title="Margin",
                yaxis_title="",
            )
        figMargin.update_layout(yaxis=dict(showticklabels=False))
        #Update the layout to hide the legend:
        figMargin.update(layout_coloraxis_showscale=False)
        figMargin.update_xaxes(
                tickfont=dict(
                    size=22,         # Font size
                ),
                title = None,
                dtick=.2
            )
        figMargin.update_layout(title=dict(y=.90))
        figMargin.update_layout(margin=dict(t=130, b=100, l=40, r=40))

        apply_logo_to_fig(figMargin,yval= -0.07)

        return figMargin
        
    def HallofShame_Team(self):
        Worst10 = self.Matches.sort_values('Total')[0:10]
        Worst10['Total'] = Worst10['Total'].astype(int)
        Worst10['TeamName'] = '<b>' + Worst10['Team'] + '</b><br>W' + Worst10['Week'].astype(str) + " " + Worst10['Year'].astype(str)
        Worst10 = Worst10.sort_values('Total')
        
        
        
        figWorst = px.bar(Worst10, x='Total',y='TeamName', color = 'Team', orientation='h', template='gridiron_ink', title = '<b>Hall of Shame</b><br><sup>Team</sup>', text = 'Total', color_discrete_map=self.teamcolors)
        figWorst.update_layout(height = 1200, width= 800, showlegend=False)
        figWorst.update_layout(title_font = dict(size=45))
        figWorst.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
            )
        figWorst.update_yaxes(showticklabels=False, title=None, categoryorder="total descending")
        for label, team in zip(Worst10['TeamName'], Worst10['Team']):
            figWorst.add_annotation(
                x=0, y=label, xref='paper', yref='y',
                text=label, showarrow=False,
                xanchor='right', align='right', xshift=-8,
                font=dict(color=self.teamcolors.get(team, '#BDE2FF'), size=16, family='Courier New'),
            )

        figWorst.update_traces(textposition='inside', textfont_size=80)
        figWorst.update_layout(margin=MARGIN_HBAR)
        
        apply_logo_to_fig(figWorst,xval=.40)

        return figWorst
    
    def HallofFame_Team(self):
        Best10 = self.Matches.sort_values('Total', ascending=False)[0:10]
        Best10['Total'] = Best10['Total'].astype(int)
        Best10['TeamName'] = '<b>'+ Best10['Team'] + '</b>' + '<br>' + "W" +Best10['Week'].astype(str) + " " + Best10['Year'].astype(str)
        
        figBest = px.bar(Best10, x='Total',y='TeamName', color = 'Team', orientation='h', template='gridiron_ink', title = '<b>Hall of Fame</b><br><sup>Team</sup>', text = 'Total', color_discrete_map=self.teamcolors)
        figBest.update_layout(height = 1200, width= 800, showlegend=False)
        figBest.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                
            )
        figBest.update_yaxes(showticklabels=False, title=None, categoryorder="total ascending")
        for label, team in zip(Best10['TeamName'], Best10['Team']):
            figBest.add_annotation(
                x=0, y=label, xref='paper', yref='y',
                text=label, showarrow=False,
                xanchor='right', align='right', xshift=-8,
                font=dict(color=self.teamcolors.get(team, '#BDE2FF'), size=16, family='Courier New'),
            )
        figBest.update_layout(font=dict(size=20))
        figBest.update_layout(margin=MARGIN_HBAR_MED)
        figBest.update_traces(textposition='inside', textfont_size=80)

        
        apply_logo_to_fig(figBest,xval=.40)
        return figBest
        
    def HallofFame_Player(self):
            
        Best10Players = self.Breakout.sort_values('points', ascending=False)[0:10]
        Best10Players['TeamName'] = '<b>' + Best10Players['team'] + '</b><br><sup>' + "W" +Best10Players['week_x'].astype(str) + " " + Best10Players['year'].astype(str) + '</sup>'
        Best10Players['Player-Points'] = '<b>' + Best10Players.player + '</b><br>' + Best10Players.points.astype(str)
        
        figBestPlayers = px.bar(Best10Players, x='points',y='TeamName', color = 'team', orientation='h',
                        template='gridiron_ink', title = '<b>Hall of Fame</b><br><sup>Players</sup>', text = 'Player-Points',
                        color_discrete_map=self.teamcolors)
        figBestPlayers.update_layout(height = 1200, width= 800, showlegend=False)
        figBestPlayers.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                
            )
        figBestPlayers.update_yaxes(showticklabels=False, title=None, categoryorder="total ascending")
        for label, team in zip(Best10Players['TeamName'], Best10Players['team']):
            figBestPlayers.add_annotation(
                x=0, y=label, xref='paper', yref='y',
                text=label, showarrow=False,
                xanchor='right', align='right', xshift=-8,
                font=dict(color=self.teamcolors.get(team, '#BDE2FF'), size=16, family='Courier New'),
            )

        figBestPlayers.update_layout(margin=MARGIN_HBAR_MED)
        figBestPlayers.update_traces(textposition='inside', textfont_size=55)

        
        apply_logo_to_fig(figBestPlayers,xval=.40)

        return figBestPlayers
        
    def ForAgainstwithTeams(self):
        OpponentPoints = self.Breakout.groupby(['team','opponent_team'])['points'].sum().reset_index().sort_values('points', ascending=False)
        OpponentPointsNoTeam = self.Breakout.groupby(['team','opponent_team'])['points'].sum().round(1).reset_index().sort_values('points', ascending=False)
        OpponentPointsNoTeamTOP =  OpponentPointsNoTeam.iloc[0:10]
        OpponentPointsNoTeamTOP['TeamVs'] = OpponentPointsNoTeamTOP.team + ' vs. ' + OpponentPointsNoTeamTOP.opponent_team
        OpponentPointsNoTeamTOP['Purpose'] = 'Points Against...'    
        
        TeamPoints = self.Breakout.groupby(['team','recent_teams'])['points'].sum().round(1).reset_index().sort_values('points', ascending=False)
        TeamPointsTOP = TeamPoints.iloc[0:10]

        TeamPointsTOP['color'] = TeamPointsTOP.team.map(self.teamcolors)
        OpponentPointsNoTeamTOP['color'] = OpponentPointsNoTeamTOP.team.map(self.teamcolors)
        TeamPointsTOP['TeamVs'] = TeamPointsTOP.team + ' w/ ' + TeamPointsTOP.recent_teams
        TeamPointsTOP['Purpose'] = 'Points With...'

        figTeamPoints = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=False,
                    vertical_spacing=.1,
                    specs=[[{"type": "bar"}],
                            [{"type": "bar"}]],
                    subplot_titles=['Points With...','Points vs...']
                )
        figTeamPoints.add_trace(
                    go.Bar(
                        x=TeamPointsTOP['points'],
                        y=TeamPointsTOP['TeamVs'],
                        text=TeamPointsTOP['points'],
                        textangle=0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h',
                        marker_color=TeamPointsTOP['color'],
                        opacity=.8,
                        textfont=dict(size=20)
                    ),
                    row=1, col=1
                )
        figTeamPoints.add_trace(
                    go.Bar(
                        x=OpponentPointsNoTeamTOP['points'],
                        y=OpponentPointsNoTeamTOP['TeamVs'],
                        text=OpponentPointsNoTeamTOP['points'],
                        textangle=0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h',
                        marker_color=OpponentPointsNoTeamTOP['color'],
                        opacity=.8,
                    ),
                    row=2, col=1
                )

        figTeamPoints.update_layout(height = 1200, width = 900, template = 'gridiron_ink', barcornerradius = 7)
        figTeamPoints.update_xaxes(side='bottom')
        figTeamPoints.update_layout(yaxis2 = {'categoryorder': 'total ascending'})
        figTeamPoints.update_annotations(font_size=25)
        figTeamPoints.update_layout(title="<b>Points With & Against NFL Teams</b>")

        figTeamPoints.update_layout(xaxis1=dict(side='bottom'),xaxis2=dict(side='bottom'))

        figTeamPoints.update_layout(margin=dict(t=140, b=100, l=320, r=40))
        
        apply_logo_to_fig(figTeamPoints,xval=.40, yval=-0.06)


        return figTeamPoints
            
    
       
        
        
        
class SideBet:
    def __init__(self,League,Season, DictofWeeks = None, ):
               
        self.DictofWeeks = DictofWeeks
        self.League = League
        self.Season = Season
        
        self.SetTeamColors()

    
    
    
    def UpdateColors2(self,WeekObj ,fig):
        """
        Updates the y-axis tick labels of a figure to use team-specific colors.
        """
        # --- THE FIX ---
        # Instead of 'categoryarray', we get labels directly from the figure's data trace.
        # This is a more reliable way to access the list of teams on the y-axis.
        if not fig.data or fig.data[0].y is None:
            # Failsafe in case the figure has no data
            return fig

        y_axis_labels = fig.data[0].y
        
        # Create a new list of HTML-styled labels with the correct colors.
        styled_labels = []
        for label in y_axis_labels:
            # Look up the color for the team from your dictionary
            color = WeekObj.teamcolors.get(label, 'white') # Default to white if not found
            styled_labels.append(f"<span style='color:{color}'>{label}</span>")

        # Update the y-axis to use the new styled text.
        # 'tickvals' provides the original labels to map against.
        # 'ticktext' provides the new, styled labels to display.
        fig.update_yaxes(
            tickvals=y_axis_labels,
            ticktext=styled_labels
        )
                
        return fig
    
    def SetTeamColors(self, color_dict:dict = None):
        self.teamcolors = get_slot_teamcolors(self.League.year)
        if color_dict is not None:
            self.teamcolors = color_dict

    def Scoreboard(self, tally = None):
            
            def calc_table_height(df, base=208, height_per_row=20, char_limit=30, height_padding=16.5):
                '''
                df: The dataframe with only the columns you want to plot
                base: The base height of the table (header without any rows)
                height_per_row: The height that one row requires
                char_limit: If the length of a value crosses this limit, the row's height needs to be expanded to fit the value
                height_padding: Extra height in a row when a length of value exceeds char_limit
                '''
                total_height = 0 + base
                for x in range(df.shape[0]):
                    total_height += height_per_row
                for y in range(df.shape[1]):
                    if len(str(df.iloc[x][y])) > char_limit:
                        total_height += height_padding
                return total_height

            if tally != None:
                 tally_list = tally
            else:
                tally_list = [['JTizzzzle',1],
                ['eegrady',1],
                ['cosmodromedary',1],
                ['bgmaddox',3],
                ['sgmaddox',1],
                ['jhuntmadd',3],
                ['RascalHazard',0],
                ['InfiniteJesse',0],
                ['BMoreBallers88',1],
                ['RossLikeSauce',0],
                ['DirtyCommie',3],
                ['jlglover',0]]

            tallyDF = pd.DataFrame(tally_list, columns=['Team','Wins'])
            tallyDF['Prize $'] = '$' + (tallyDF.Wins * 20).astype(str)

            SideBetWeeklyWins_list = [["<b>WEEK 1:</b> I'm flying, Jack! - Team with the highest score (starters only)",'cosmodromedary'],
            ['<b>WEEK 2:</b> Look At These TDs - Team with the most offensive touchdowns scored','DirtyCommie'],
            ['<b>WEEK 3:</b> Big Helpers, too (just ask my mom): Most combined points with starting D/ST & Kicker','jhuntmadd'],
            ['<b>WEEK 4:</b> Blackjack - Team with a starter closest to 21 points without going over','sgmaddox & jhuntmadd'],
            ['<b>WEEK 5:</b> The Replacements - Team with the highest total points for their bench','DirtyCommie'],
            ['<b>WEEK 6:</b> The Boom & Bust: Team with the largest point differential between their single highest-scoring starter and their single lowest-scoring starter.','eegrady'],
            ['<b>WEEK 7:</b> Campus Rush Week - Total rush yards for team (active or bench)','bgmaddox'],
            ['<b>WEEK 8:</b> All Hands on Deck: Team with the most starting players who score over 15 points','bgmaddox'],
            ['<b>WEEK 9:</b> The Old Man & Young Buck: Best combined score from a starting player over 30 and a rookie','JTizzzzle'],
            ['<b>WEEK 10:</b> NFL Franchise Week - Team with the highest point total of players from the same franchise (active or bench)','DirtyCommie'],
            ['<b>WEEK 11:</b> Please not the Jets (Trade Deadline Week) - Team with the most trades this seasons wins','jhmadd & BMoreBallers88'],
            ['<b>WEEK 12:</b> Go Long - Team with the Starting QB with the highest completion % (over 10 throws)','bgmaddox'],
            ["<b>WEEK 13:</b> Coffee's For Closers - Team that beats its opponent by the smallest margin of victory",''],
            ['<b>WEEK 14:</b> Breaking of the Tie (if needed) - Choose 3 non-QB players. Highest combined total wins.','']]

            SideBetWeeklyWins = pd.DataFrame(SideBetWeeklyWins_list, columns=['Side Bet','Winner'])

            figSideBets = make_subplots(
                rows=1, cols=2, 
                shared_xaxes=False,
                horizontal_spacing=0.08, 
                vertical_spacing=0.05,
                shared_yaxes=True,
                column_widths=[0.35, 0.5],  # Adjust the width of each subplot
                specs=[[{"type": "pie"}, {"type": "table"}]]
                    
                #subplot_titles=['Matchup Schedule','Win History']# Specify the chart types
            )
            tallyDF = tallyDF.sort_values('Wins')
            headerColor = 'grey'
            rowEvenColor = 'lightgrey'
            rowOddColor = 'white'
            df = SideBetWeeklyWins

            figSideBets.add_trace(
                go.Pie(values=tallyDF['Wins'],text=tallyDF['Team']),
                
                row=1, col=1)
            figSideBets.add_trace(go.Table(
                columnorder = [1,2],
                columnwidth = [65,25],
                header=dict(values=list(df.columns),
                            #fill_color='paleturquoise',
                            align=['center','center'],
                            font=dict(size=25, weight = 'bold', color = 'black')),
                cells=dict(values=[df['Side Bet'], df.Winner],
                        fill_color = [[rowOddColor,rowEvenColor,rowOddColor, rowEvenColor]*5],
                        align=['left','center'],
                        height = 30,
                        font=dict(color='black', size=14))
                                        ), row=1, col=2)
            figSideBets.update_layout(height = calc_table_height(SideBetWeeklyWins))
            # figSideBets.update_polars(bgcolor='#BDE2FF')


            # figSideBets.update_layout(
            #     # showlegend = True,
            #     polar=dict(
            #         angularaxis=dict(
            #             showline=False,
            #             tickfont = dict(
            #                  size = 15,
            #                  color = 'white',
            #                 weight = 'bold'
            #             )),
            #         radialaxis=dict(
            #             tickvals=[0,1,2,3,4],  # Specify the tick values
            #             ticktext=['', '1 Win','2 Wins', '3 Wins', '4 Wins'],  # Customize tick labels
            #             tickfont = dict(
            #                  size = 22,
            #                  color = 'black',
            #                 weight = 'bold'
            #             )
            #         )))
            
            figSideBets.update_layout(width=None, height=1200, title_text = '<b>Side Bet Tally</b>')

            apply_logo_to_fig(figSideBets)
            figSideBets.update_layout(title ={'y':.93, 'font':dict(size=65)})
            self.Tally = tallyDF
            return figSideBets
        
    
    
    def Week1(self, WeekObj,top):
        
        df = WeekObj.WeeklyNoMatches
        df = df.sort_values('Total', ascending = False)
        top = df['Team'][0]
        
        #points = df.drop(columns=['Total','Won','Week','Opp','Matchup']).map(lambda x: float(list(x.values())[0]))
        points = df.map(lambda x: float(list(x.values())[0]) if isinstance(x, dict) else x)
        points = points.round(1).reset_index()
        
        default_color = '#F94144'
    
        colors = {top: "#17BECF"}
        
        #points = df.sort_values('Total', ascending = False)
        team_list = df.sort_values('Total', ascending = True).index.tolist()
        
        #Ranked = df.index.sort_values('Total', ascending = True).unique()
        SizeZip = dict(zip(team_list,range(12,30)))
        print(SizeZip)

        color_discrete_map = {
            c: colors.get(c, default_color) 
            for c in team_list}


        fig1 = px.bar(points, y='Team',x=position_list,template = 'gridiron_ink',color = "Team", text_auto=True, title = f'Week {Week} Side Bet', orientation='h',color_discrete_map=color_discrete_map)
        
        #Update the layout to hide the legend:
        fig1.update(layout_coloraxis_showscale=False)
        
        # Adjust the figure size
        fig1.update_layout(title=dict(
                font=dict(
                    size=50,)))  # Set the width and height in pixels
        fig1.update_traces(textfont_size=12, textangle=0, cliponaxis=True, textposition = 'auto', textfont=dict(weight='bold',  # Font family
                size=12   # Font color
            ))
        
        # Customize the x-axis labels
        fig1.update_xaxes(
            tickfont=dict(
                size=16,         # Font size
            ),
            title = None
        )

        # Customize the y-axis labels
        fig1.update_yaxes(
            tickfont=dict(
                size=18,         # Font size
            ),
            title=None
        )

        fig1.update(layout_coloraxis_showscale=False)
        fig1.update_layout(showlegend=False)
        fig1.update_traces(insidetextanchor= 'middle')
        
        
        annotations = []
        for i, val in enumerate(points.Total):
            annotations.append(
                dict(
                    x=val+10, 
                    y=points.Team[i], 
                    text=str(val), 
                    xanchor='left', 
                    yanchor='middle', 
                    showarrow=False, 
                    font=dict(size=SizeZip[points.Team[i]],)
                    )   
                            )

        fig1.update_layout(annotations=annotations)

        fig1.update_traces(marker_line_width=1.5,marker_line_color='rgba(0,0,0,0.25)')
        
        fig1.update_traces(insidetextanchor= 'middle')
        fig1.update_layout(
            uniformtext_minsize=12,
            uniformtext_mode='hide'
            )
        fig1.add_annotation(
        text="Bar Order: QB ------------> DEF",
        xref="paper", yref="paper",
        x=0.05, y=-.06, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
        )
        )

        return fig1
    

    
    
    def Week2(self, WeekObj):
        Week2 = WeekObj.Breakout
        #Week2 = WeeklyNFLData_24[WeeklyNFLData_24['week'] == 2]
        td_cols = [col for col in Week2.columns if 'tds' in col.lower()]
        td_cols.remove('def_tds')
        td_cols.remove('fumble_recovery_tds')
        info_cols = []
        info_cols.append('player_display_name')
        info_cols.append('team')
        info_cols.append('position')
        info_cols.append('player')

        df_cols = info_cols + td_cols

        #Week2filtered= Week2[td_cols]
        #Week2Data = week2Breakout2024.merge(Week2filtered,left_on='player', right_on='player_display_name')
        Week2Data = Week2[Week2['starter']==1]
        Week2Data = Week2Data[df_cols]
        Week2Data.loc[94,'receiving_tds'] = 1.0
        Week2Data.fillna(0, inplace=True)

        Week2Data['Total']= Week2Data['passing_tds'] + Week2Data['rushing_tds'] + Week2Data['receiving_tds'] + Week2Data['special_teams_tds']

        Week2Totals = Week2Data.groupby(['team','position']).agg('sum')

        Week2Groups = Week2Data.groupby('team')
        Week2Groups.get_group('bgmaddox').sort_values('position')

        Week2Totals.sort_values('Total', ascending=False)
        Week2Totals.sort_values('Total', ascending=False)
        Week2Totals = Week2Totals.sort_values('Total', ascending=False).reset_index()
        
        Week2Data = Week2Data.sort_values(['player'], ascending=False)

        
        # Graph

        fig = px.bar(Week2Totals,y='team',x='Total',color='position' ,title = f'Week {WeekObj.week} Side Bet', orientation='h',text=f'Total')

        fig.update_traces(insidetextanchor= 'middle',textfont=dict(
                size=35, weight = 'bold'))

        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        fig.update_layout(
            showlegend = True,
            legend=dict(
                x=.4,
                y=1.06,
                xref = 'paper',
                xanchor = 'center',
                orientation = 'h',
                #traceorder="reversed",
                title = 'Position',
                font=dict(
                    size=18,
                )#,
                #bgcolor="LightSteelBlue",
                #bordercolor="Black",
                #borderwidth=2
            )
        )
        fig.update_layout(
                xaxis_title="",  # Set x-axis title
                yaxis_title="")
        fig.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None
            )

            # Customize the y-axis labels
        fig.update_yaxes(
                tickfont=dict(
                    size=25, weight ='bold'       # Font size
                ),
                title=None
            )
        fig.update_traces(marker_line_width=2,marker_line_color='rgba(0,0,0,0.25)')
        fig.update_layout(margin=dict(t=130, b=100, l=220, r=40), title ={'y':.94})
        
        
        apply_logo_to_fig(fig,xval=.43, yval=-0.06)
        self.UpdateColors2(WeekObj,fig)
        self.Week2Data = Week2Data
        self.Week2Totals = Week2Totals

        fig.show()

    def Week3(self, WeekObj):

        ## Best DF/K Combo

        positions = ['DEF','K']

        df = WeekObj.Breakout
        df = df[df['starter'] == 1]
        df = df[df['position'].isin(positions)]
        df['display_text'] = '<b>' + df['points'].astype(str) + '</b><br><sup>' + df['player'] +'</sup>'


        ## GRAPH

        fig = px.bar(df,y='team',x='points',color='position' ,title = f'<b>Week {WeekObj.week} Side Bet</b><br><sup>Best DEF/K Combo</sup>', orientation='h',text='display_text', barmode='relative')

        fig.update_layout(
                xaxis_title="",  # Set x-axis title
                yaxis_title="")

        fig.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None
            )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})

        fig.update_layout(
            showlegend = True,
            legend=dict(
                x=.8,
                y=1.06,
                xref = 'paper',
                xanchor = 'center',
                orientation = 'h',
                #traceorder="reversed",
                title = '',
                font=dict(
                    size=18,
                )#,
                #bgcolor="LightSteelBlue",
                #bordercolor="Black",
                #borderwidth=2
            )
        )
        fig.update_traces(insidetextanchor= 'middle',textfont=dict(
                size=35, weight = 'bold'))
        
        fig.update_traces(textfont_size=35, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(weight='bold',  # Font family
                size=35   # Font color
            ))
        apply_logo_to_fig(fig,xval=.43, yval=-0.06)
        fig.update_layout(margin=dict(t=130, b=100, l=230, r=40), title ={'y':.94})

        fig.update_yaxes(
                tickfont=dict(
                    size=25, weight ='bold'       # Font size
                ),
                title=None
            )
        self.UpdateColors2(WeekObj,fig)
        self.Week3df = df
        

        fig.show()

    def Week4(self, WeekObj):

        Week = WeekObj.week

        Week4SideBet = WeekObj.Breakout[WeekObj.Breakout['points'] <= 22]
        Week4SideBet = Week4SideBet[Week4SideBet['points'] >= 17]
        Week4SideBet = Week4SideBet.sort_values('points', ascending = False)

        df = Week4SideBet.head(15).sort_values('points', ascending = False)

        df['string_pts'] = df['points'].astype(str)
        df['team-points'] = df['team'] + "<br><sup>" + df['string_pts'] + '</sup>'
        df = df.sort_values('points', ascending = True)
      
        team_list = df['team'].unique()

        


        fig1 = px.bar(df, y='player',x='points',template = 'gridiron_ink', color = 'team', text='team-points', #text_auto=True, 
                        title = f'<b>Week {Week} Side Bet</b><br><sup>Blackjack</sup>', orientation='h'
                    )
        
        #Update the layout to hide the legend:
        fig1.update(layout_coloraxis_showscale=False)
        
        # Adjust the figure size
        # fig1.update_layout(width=800, height=1200)
        fig1.update_traces(textfont_size=20, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(weight='bold',  # Font family
                size=20   # Font color
            ))
        fig1.update_layout(yaxis={'categoryorder':'total ascending'})
        # Customize the x-axis labels
        fig1.update_xaxes(
            tickfont=dict(
                size=16,         # Font size
            ),
            title = None
        )

        # Customize the y-axis labels
        fig1.update_yaxes(
            tickfont=dict(
                size=18,         # Font size
            ),
            title=None
        )

        #fig1.update(layout_coloraxis_showscale=False)
        fig1.update_layout(showlegend=False)
        
        fig1.update_layout(legend=dict(
        orientation="h",
        #yanchor="bottom",
        #y=-.1,
        xanchor="center",
        x=.5,
        title = ""
    ))
        fig1.add_vline(x=21, line_width=3, line_dash="dash",
        line_color="red", annotation_text="Bust Line", annotation_position="top right",annotation_font_size=25,
        annotation_font_color="red")

        fig1.update_layout(margin=dict(t=130, b=100, l=220, r=40), title ={'y':.94})
        
        
        apply_logo_to_fig(fig1,xval=.43, yval=-0.06)


        return fig1
    

    def Week5(self, WeekObj):
        Week5SideBetdf = WeekObj.Breakout
        Week5SideBetdf = Week5SideBetdf[Week5SideBetdf['starter']==0]
        Week5List = Week5SideBetdf.groupby('team')['points'].sum().reset_index()
        Week5List.sort_values('points')
        figWeek5 = px.bar(Week5SideBetdf, x='points',y='team',template = 'gridiron_ink',title=f'<b>Week {WeekObj.week} Side Bet</b><br><sup>Best Bench</sup>', color = 'position',
                           orientation='h', text = 'player' )
        figWeek5.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'})
            # Adjust the figure size
        figWeek5.update_layout(width=None, height=800, showlegend = True)
        
        figWeek5.update_traces(textfont_size=12, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(weight='bold',  # Font family
                    size=12   # Font color
                ))
        # Update the line thickness
        figWeek5.update_layout(
                xaxis_title="Points",  # Set x-axis title
                yaxis_title="Teams",   # Set y-axis title
                xaxis=dict(
                    title_font=dict(
                        size=30,          # Set font size for x-axis title
                        color ='red',
                        weight = 'bold'
                    )
                ),
                yaxis=dict(
                    title_font=dict(
                        size=30,          # Set font size for y-axis title
                        color = 'green',
                        weight = 'bold'
                    )
                )
            )
        figWeek5.update_layout(
            legend=dict(
                x=0.37,
                y=1.08,
                xanchor = 'center',
                #traceorder="reversed",
                title = 'Position',
                font=dict(
                    size=15,
                )#,
                #bgcolor="LightSteelBlue",
                #bordercolor="Black",
                #borderwidth=2
            )
        )

        figWeek5.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None
            )

            # Customize the y-axis labels
        figWeek5.update_yaxes(
                tickfont=dict(
                    size=25,         # Font size
                ),
                title=None
            )
        apply_logo_to_fig(figWeek5,xval=.43, yval=-0.06)
        figWeek5.update_layout(margin=dict(t=160, b=100, l=230, r=40), title ={'y':.93})
        self.UpdateColors2(WeekObj,figWeek5)

        
        return figWeek5

    def Week5Graph(self, df, WeekObj,top):
        df = WeekObj.Match
        df = df.sort_values('Total', ascending = False)
        points = df.drop(columns=['Total','Won','Week','Opp','Matchup']).map(lambda x: float(list(x.values())[0]))
        points = points.round(2).reset_index()
        
        default_color = "blue"
        colors = {top: "red"}

        team_list = points['Team'].unique()

        color_discrete_map = {
            c: colors.get(c, default_color) 
            for c in team_list}


        fig1 = px.bar(points, y='Team',x=position_list,template = 'gridiron_ink',color = "Team", text_auto=True, title = f'Week {Week} Side Bet', orientation='h',color_discrete_map=color_discrete_map)
        
        #Update the layout to hide the legend:
        fig1.update(layout_coloraxis_showscale=False)
        
        fig1.update_layout(barcornerradius=13)
        # Adjust the figure size
        fig1.update_layout(width=800, height=1200)
        fig1.update_layout(title=dict(
                font=dict(
                    size=50,
                    family="Courier New")))  # Set the width and height in pixels
        fig1.update_traces(textfont_size=12, textangle=0, cliponaxis=True, textposition = 'auto', textfont=dict(weight='bold',  # Font family
                size=12   # Font color
            ))
        
        # Customize the x-axis labels
        fig1.update_xaxes(
            tickfont=dict(
                size=16,         # Font size
            ),
            title = None
        )

        # Customize the y-axis labels
        fig1.update_yaxes(
            tickfont=dict(
                size=18,         # Font size
            ),
            title=None
        )

        fig1.update(layout_coloraxis_showscale=False)
        fig1.update_layout(showlegend=False)
        # Adjust the figure size
        fig1.update_layout(width=800, height=1200)
        fig1.update_layout(title=dict(
                ))  # Set the width and height in pixels
        fig1.update_traces(textfont_size=12, textangle=0, cliponaxis=True, textposition = 'inside', textfont=dict(weight='bold',  
                size=12   # Font color
            ))
        


        fig1.show()
        return fig1

    def Week6(self, WeekObj):
        df6 = WeekObj.Breakout
        df6 = df6[df6.starter == 1]
        df6group = df6.groupby('team')
        BustBoom = pd.DataFrame()

        for team in df6.team.unique():
            teamdf = df6group.get_group(team)
            maxrow = teamdf[teamdf.points == teamdf.points.max()]
            minrow = teamdf[teamdf.points == teamdf.points.min()]
            teamrows = pd.concat([maxrow,minrow])
            teamrows['difference'] = teamrows.points.sum().round(1)

            BustBoom = pd.concat([BustBoom,teamrows])


        figWeek6 = px.bar(BustBoom, y='team',x='points',template = 'gridiron_ink',color = "team", title = f'Week {WeekObj.week} Side Bet', orientation='h',barmode='overlay', text = 'player')
        figWeek6.update_traces( textfont_size=20  # Font color
            )
        
        figWeek6.update_layout(
                xaxis_title="",  # Set x-axis title
                yaxis_title="")
        
        # self.UpdateColors2(WeekObj,figWeek6)

        apply_logo_to_fig(figWeek6)

        return figWeek6
    

    def Week7(self, WeekObj):
        Week7Data = WeekObj.Breakout
        Week7Groups = Week7Data.groupby('team')['rushing_yards'].sum()
        Week7Groups = Week7Groups.reset_index()


        figWeek7 = px.bar(Week7Data,y='team',x='rushing_yards',color='position' ,template = 'gridiron_ink',title = f'<b>Week {WeekObj.week} Side Bet</b><br><sup>Rush Week</sup>', 
                          orientation='h')
        
        figWeek7.update_layout(width=800, height=1200)
        
        
        figWeek7.update_layout(yaxis={'categoryorder':'total ascending'})
        
        figWeek7.update_layout(
                xaxis_title="",  # Set x-axis title
                yaxis_title="")
        figWeek7.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
              ),
                title = None
            )

            # Customize the y-axis labels
        figWeek7.update_yaxes(
                tickfont=dict(
                 size=18,         # Font size
                ),
                title=None
            )
        # figWeek7.update_traces(marker_line_width=2,marker_line_color='black')
        
        
        # Add annotations for rushing yards
        for i, row in enumerate(Week7Groups['team']):
            figWeek7.add_annotation(
                x=Week7Groups['rushing_yards'][i].sum()+5,  # Rushing yards for x position
                y=Week7Groups['team'][i],  # Team name for y position
                text=f"{Week7Groups['rushing_yards'][i]} yards",  # Annotation text
                showarrow=False,  # No arrow
                font=dict(
                    size=13,
                ),
                xanchor='left',  # Align to the left of the bar
                yanchor='middle'
            )
        self.Week7Data = Week7Groups

        self.UpdateColors2(WeekObj,figWeek7)
        apply_logo_to_fig(figWeek7, xval=.4)
        figWeek7.update_layout(margin=dict(t=160, b=100, l=180, r=40), title ={'y':.93})


        return figWeek7
    
    def Week8(self,WeekObj):

        df8 = WeekObj.Breakout
        df8 = df8[df8.starter == 1]
        # Create a new column 'over_15' which is 1 if true, 0 if false
        df8['over_15'] = (df8['points'] >= 15).astype(int)
        # Now, sum this column for ALL teams
        df8group = dict(df8.groupby('team')['over_15'].sum())

        figWeek8 = px.bar(df8,x='player',y='points',facet_col='team',facet_col_wrap=3, color = 'position', title = f'<b>Side Bet Week {WeekObj.week}</b><br><sup>Players Over 15 pts</sup>',
                    facet_row_spacing=.1)
        figWeek8.update_xaxes(matches=None,showticklabels = False, title = '')
        figWeek8.update_yaxes(title = '')
        figWeek8.update_layout(showlegend = True)

        figWeek8.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
       
        figWeek8.update_layout(margin=dict(t=180, b=100, l=40, r=40))
        figWeek8.update_layout(
                    legend=dict(
                        x=0.5,  # x-coordinate of the legend (0 to 1, where 0 is left and 1 is right)
                        y=1.13,   # y-coordinate of the legend (0 to 1, where 0 is bottom and 1 is top)
                        xanchor="center",  # horizontal anchor point ('left', 'center', 'right')
                        yanchor="top",   # vertical anchor point ('top', 'middle', 'bottom')
                        title = None
                    )
                )
                
        apply_logo_to_fig(figWeek8)
        for annotation in figWeek8.layout.annotations:
                    title_text = annotation.text  # e.g., "Team A vs Team B"
                    #teams = title_text.split(" vs ")  # Split into individual team names
                    # Create a styled title with team names in respective colors
                    annotation.text = f"<span style='color:{self.teamcolors[title_text]}'>{title_text}</span><br>{df8group[title_text]}"
                    annotation.font.size = 23  # Optional: Adjust font size for clarity
        
        figWeek8.add_hline(y=15,line_color = 'red' ,annotation_text='15 pts.')

        return figWeek8

    def Week9(self,WeekObj):
        Week9Setup = WeekObj.Breakout
        Week9Setup = Week9Setup[Week9Setup.starter == 1]
        Week9Setup = Week9Setup[(Week9Setup['rookie_year'] == 2025.0) | (Week9Setup['age']>29.0)]
            
        Week9Setup['Type'] = np.where(Week9Setup['rookie_year'] == 2025.0, 'Young Buck', 'Old Man')

        idx = Week9Setup.groupby(['team','Type'])['points'].idxmax()

        Week9 = Week9Setup.loc[idx]

        Week9['Player_Text'] = '<b>' + Week9['player'] + '</b><br><sup>' + Week9['Type'] + '</sup>'

        figWeek9 = px.bar(Week9, x = 'points', y = 'team', orientation='h', color = 'Type', text = 'Player_Text', title = f'<b>Week {WeekObj.week} Side Bet</b><br><sup>The Old Man & Young Buck</sup>')
        figWeek9.update_layout(yaxis={'categoryorder':'total ascending'})

        figWeek9.update_layout(
                xaxis_title="",  # Set x-axis title
                yaxis_title="")
        
        figWeek9.update_yaxes(
                tickfont=dict(
                    size=22, weight ='bold'       # Font size
                )
            )

        apply_logo_to_fig(figWeek9)
        self.UpdateColors2(WeekObj,figWeek9)
        figWeek9.update_layout(margin=dict(t=160, b=100, l=210, r=40), title ={'y':.93})



        return figWeek9
    
    def Week10(self, WeekObj):
        

        Week10SideBet2 = WeekObj.Breakout.groupby(['team','recent_team'])[['player','points']].sum(numeric_only=True).reset_index()

        Week10SideBet2Data = Week10SideBet2.sort_values('points', ascending=False).head(10)
        Week10SideBet2Data['Name'] = Week10SideBet2Data['team'] + ' - ' + Week10SideBet2Data['recent_team']

        
        Week10SideBet = WeekObj.Breakout.groupby(['team'])[['player','points','recent_team']]
        Week10SideBet2 = WeekObj.Breakout.groupby(['team','recent_team'])[['player','points']].sum(numeric_only=True).reset_index()
        Week10SideBet2Data = Week10SideBet2.sort_values('points', ascending=False).head(10)
        Week10SideBet2Data['Name'] = Week10SideBet2Data['team'] + ' - ' + Week10SideBet2Data['recent_team']

        #grouped = breakoutDF_group.groupby('matchup')
                # Create a subplot with 1 row and 2 columns (for the bar chart and the pie chart)
        figCombo2 = make_subplots(
                    rows=7, cols=2, 
                    shared_xaxes=False,
                    horizontal_spacing=0.04, 
                    vertical_spacing=0.05,
                    shared_yaxes=True,
                    column_widths=[0.5, 0.5],  # Adjust the width of each subplot
                    specs=[[{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"type": "bar"}, {"type": "bar"}],
                        [{"colspan":2,"type":"bar"},None]]
                    #subplot_titles=['Matchup Schedule','Win History']# Specify the chart types
                )
        for i in range(1,13):
                person = roster_ids_2025[i]
                CurrentGraph = Week10SideBet.get_group(person)
                rowlist = [1,1,2,2,3,3,4,4,5,5,6,6]
                collist = [1,2,1,2,1,2,1,2,1,2,1,2]
                rowdict = dict(enumerate(rowlist,1))
                coldict = dict(enumerate(collist,1))
                
                # Add the bar chart to the first column
                figCombo2.add_trace(
                    go.Bar(
                        y=CurrentGraph['points'], 
                        x=CurrentGraph['recent_team'], 
                        
                        #marker=dict(
                        #    color = [teamcolors[team] for team in CurrentGraph['team']], 
                        #    cornerradius = 10
                        #),
                        
                        text=CurrentGraph['points'],
                        textangle = 0,
                        textposition='auto',
                        showlegend=False,
                    ),
                    row=rowdict[i], col=coldict[i]
                )

                
                    # Create a custom title with colored team names
                #title_html = f'<span style="color:{teamcolors[teams[0]]}">{teams[0]}</span> vs <span style="color:{teamcolors[teams[1]]}">{teams[1]}</span>'

                # Add the custom title as an annotation at the top of each subplot
                figCombo2.add_annotation(
                    text=roster_ids_2025[i], #,  # The HTML title
                    xref=f'x domain', yref=f'y domain',
                    x=.5, y=1.2,  # Position it above the subplot (y > 1)
                    xanchor='center',
                    font=dict(size=20, weight ='bold'),
                    showarrow=False,
                    row=rowdict[i], col=coldict[i] # Apply to the i-th row and first column (bar chart)
                )
                # Update the layout with dark theme and grouped bar mode
                figCombo2.update_layout(barmode="group", template="gridiron_ink",barcornerradius=7)
                figCombo2.update_xaxes(
                    categoryorder="array",
                    side = 'bottom',
                    #categoryarray=time_order,
                    showticklabels = True, 
                    row=rowdict[i], col=coldict[i]  # Apply to the bar chart in the i-th row and first column
                )
                figCombo2.update_layout(yaxis1=dict(range=[0, 55]),yaxis2=dict(range=[0, 55]),yaxis3=dict(range=[0, 55]),yaxis4=dict(range=[0, 55]),
                                        yaxis5=dict(range=[0, 55]),yaxis6=dict(range=[0, 55]),yaxis7=dict(range=[0, 55]),yaxis8=dict(range=[0, 55]),
                                        yaxis9=dict(range=[0, 55]),yaxis10=dict(range=[0, 55]),yaxis11=dict(range=[0, 55]),yaxis12=dict(range=[0, 55])
                                        )
                figCombo2.update_layout(xaxis1=dict(tickangle=90),xaxis2=dict(tickangle=90),xaxis3=dict(tickangle=90),xaxis4=dict(tickangle=90),
                                        xaxis5=dict(tickangle=90),xaxis6=dict(tickangle=90),xaxis7=dict(tickangle=90),xaxis8=dict(tickangle=90),
                                        xaxis9=dict(tickangle=90),xaxis10=dict(tickangle=90),xaxis11=dict(tickangle=90),xaxis12=dict(tickangle=90)
                                        )
        figCombo2.add_trace(
                    go.Bar(
                        y=Week10SideBet2Data['points'], 
                        x=Week10SideBet2Data['Name'], 
                        marker_color = ('teal','tomato','tomato','tomato','tomato','tomato','tomato','tomato','tomato','tomato'),
                        
                        #marker=dict(
                        #    color = [teamcolors[team] for team in CurrentGraph['team']], 
                        #    cornerradius = 10
                        #),
                        
                        text=Week10SideBet2Data['recent_team'],
                        textangle = 0,
                        textposition='auto',
                        showlegend=False,
                        
                    ),
                    row=7, col=1
                )
        figCombo2.update_xaxes(
                    side = 'bottom',
                    tickfont = dict(size=15),
                    tickangle = -90
                    )
        
        figCombo2.update_layout(width=900, height=1200,title_text=f"<b>Week {WeekObj.week} Side Bet</b><br><sup>Franchise Week</sup>")
        apply_logo_to_fig(figCombo2,yval = -0.09)
        # self.UpdateColors2(WeekObj,figCombo2)
        figCombo2.update_layout(margin=dict(t=160, b=180, l=40, r=40), title ={'y':.93})

        return figCombo2
    
    def Week12(self,WeekObj):
        df = WeekObj.Breakout
        Week12Graph = df[df['starter']==1]
        Week12Graph = Week12Graph[Week12Graph.position == 'QB']

        cols = ['team','player','completions', 'attempts', 'recent_teams']

        Week12Simple = Week12Graph[cols]
        Week12Simple['CompletionPercent'] = round(Week12Simple['completions'] / Week12Simple['attempts'] * 100,1)
        Week12Simple = Week12Simple.sort_values('CompletionPercent', ascending=False)
        Week12Simple['GraphText'] = Week12Simple.CompletionPercent.astype(str) + '% - ' + Week12Simple.player + ' (' + Week12Simple.recent_teams + ')'

        Week12Simple['color'] = Week12Simple.team.map(WeekObj.teamcolors)
        
        

        figQBComplete = go.Figure()
        
        figQBComplete.update_layout(title_text=f"<b>Week {WeekObj.week} Side Bet</b><br><sup>Best Completion %</sup>")


        figQBComplete.add_trace(go.Bar(
            x=Week12Simple.attempts,
            y=Week12Simple.team,
            name='Trace 1', 
            marker_color = Week12Simple.color,
            orientation='h',
            opacity=.65,
            text=Week12Simple.attempts,
            textposition='outside',
            textfont=dict(size = 24)

            
        ))

        figQBComplete.add_trace(go.Bar(
            x=Week12Simple.completions,
            y=Week12Simple.team,
            name='Trace 2',
            marker_color = Week12Simple.color,
            orientation='h',
            opacity=.5,
            text=Week12Simple.completions,
            textposition='outside',
            textfont=dict(size = 24)


            )
        )

        figQBComplete.add_trace(go.Bar(
            x=-Week12Simple.CompletionPercent,
            y=Week12Simple.team,
            name='Trace 3',
            marker_color = Week12Simple.color,
            orientation='h',
            opacity=.9,
            text=Week12Simple.GraphText,
            textposition='inside',
            textfont=dict(size = 24)

            )
        )
        figQBComplete.update_layout(yaxis3={'categoryorder': 'total ascending'})


        figQBComplete.update_layout(barmode='overlay', showlegend=False)
        figQBComplete.update_layout(
            xaxis=dict(
                tickmode='array',
                tickvals=[-80, -60, -40, -20,0,20,40,60],
                ticktext=['80%', '60%', '40%', '20%', '0','20 ATT','40 ATT']
            )
        )
        figQBComplete.update_yaxes(
                tickfont=dict(
                    size=22,         # Font size
                ),
                title=None
            )
        figQBComplete.update_layout(
            xaxis=dict(
                side="top"
            )
        )
        figQBComplete.update_layout(
            font=dict(
                size=22,  # Set the font size here
            )
        )
        

        figQBComplete.update_traces(marker_line_width=1.5,marker_line_color='rgba(0,0,0,0.25)')

        apply_logo_to_fig(figQBComplete,xval=.43)
        self.UpdateColors2(WeekObj,figQBComplete)
        figQBComplete.update_layout(margin=dict(t=140, l=220, r=40), title ={'y':.93})

        return figQBComplete
    
    def Week13(self, WeekObj):
        dfWeek13 = WeekObj.WeeklyNoMatches.reset_index()
        dfWeek13 =dfWeek13[dfWeek13['Won'] == 1]
        dfWeek13['Abs Margin'] = dfWeek13.Margin.abs().round(0)
        dfWeek13['TeamName'] = dfWeek13.Margin.round(1).astype(str) + ' points over ' + dfWeek13.Opp_team

        figWeek13 = px.bar(dfWeek13.sort_values('Abs Margin', ascending=False), x='Margin',y='Team',template = 'gridiron_ink',
                           title=f'<b>Week {WeekObj.week}</b><br><sup>Smallest Margin</sup>', color = 'Matchup', orientation='h', text='TeamName' )
        #figWeek13.update_layout(barmode='stack', yaxis={'categoryorder':'mean ascending'})
        figWeek13.update_layout(width=None, height=800)

        figWeek13.update_traces(textfont_size=25, textangle=0, cliponaxis=True, textposition = 'auto', textfont=dict(weight='bold',  # Font family
                    size=25   # Font color
                ))
        figWeek13.update_layout(
                xaxis_title="Margin",  # Set x-axis title
                yaxis_title="Winners",   # Set y-axis title
                xaxis=dict(
                    title_font=dict(
                        size=30,          # Set font size for x-axis title
                        weight = 'bold'
                    )
                ),
                yaxis=dict(
                    title_font=dict(
                        size=30,          # Set font size for y-axis title
                        weight = 'bold'
                    )
                )
            )
        figWeek13.update_layout(yaxis=dict(showticklabels=True))
        #Update the layout to hide the legend:
        figWeek13.update(layout_coloraxis_showscale=False)
        figWeek13.update_yaxes(
                tickfont=dict(
                    size=25, weight = 'bold'         # Font size
                ))
        figWeek13.update_xaxes(
                tickfont=dict(
                    size=22,         # Font size
                ),
                title = None,dtick = 25
            )
        apply_logo_to_fig(figWeek13,xval=.43)
        self.UpdateColors2(WeekObj,figWeek13)
        figWeek13.update_layout( title ={'y':.93})
        figWeek13.update_layout(margin=dict(t=140, l=220, r=40))


        return figWeek13


                        
