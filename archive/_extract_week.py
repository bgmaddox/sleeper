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
        if self.year != 2025: 
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

    def ImportFixes(self):
        self.json
    
    def SetTeamColors(self, color_dict:dict = None):
        self.teamcolors = dict(zip(self.WeeklyNoMatches.sort_values('Team').reset_index().Team.unique(),coastal_colorway))
        
        
        if color_dict != None:
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
        dfBreakout = dfBreakout.merge(self.league.Rosters, on= 'player_name',how = 'left')
        
        dfBreakout = dfBreakout.merge(WeeklyNFLData, on = 'player_week_id', how = 'left', suffixes=('','_NFL'))
        dfBreakout['gametime'] = pd.to_datetime(dfBreakout['gametime']).dt.strftime('%I %p')
        dfBreakout['Game_date_time'] = dfBreakout['weekday'] + ' ' + dfBreakout['gametime'].astype(str).replace(r'0', "", regex=True)
        dfBreakout = dfBreakout.rename(columns={'team_x':'team','team_y':'recent_teams'})
        dfBreakout = dfBreakout.loc[:,~dfBreakout.columns.duplicated()].copy()
        if self.year != 2025: dfBreakout['color'] = dfBreakout['team'].map(self.teamcolors)
        
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
            starters_with_names = [self.league.player_names[player] for player in starters]
            
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
        
        
        SeasonMultiplier = {2019:0, 2020:1, 2021:2, 2022:3, 2023:4, 2024:5, 2025:6}
        
        WeeklyDf = WeeklyDf.rename(columns=positions).sort_values('Matchup')
        WeeklyDf = WeeklyDf.reset_index().rename({'index':'Team'}, axis = 1)
        WeeklyDf['Week'] = self.week
        WeeklyDf['Season'] = "Regular" if self.week < 15 else "Playoff"
        WeeklyDf['Week Index'] = self.week + (14 * SeasonMultiplier[self.year])
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
        WeeklyDf = WeeklyDf.groupby('Matchup',group_keys=False).apply(assign_opponents)
            
        WeeklyDfMatches= WeeklyDf.set_index(['Matchup','Team'])
        WeeklyDfNoMatches = WeeklyDf.set_index('Team')
        WeeklyDfClean = WeeklyDf.set_index('Team').drop(axis = 1,columns = ['Total','Won','Week','Opp','Margin'])
        
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
        if self.year != 2025:
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
    
        #points = MatchDF.drop(axis = 1,columns = ['Total','Won','Week','Opp','Margin']).applymap(lambda if isinstance(x,dict): float(list(x.values())[0]))
        points = self.WeeklyMatches.applymap(lambda x: float(list(x.values())[0]) if isinstance(x, dict) else x)
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

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.93, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        ))

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.76, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.58, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.41, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.24, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        )
        )

        fig1.add_annotation(
        text="VS.",
        xref="paper", yref="paper",
        x=-.1, y=.07, # Position relative to figure (right side, middle)
        showarrow=False,
        font=dict(
            size=15,
            color="magenta",
            weight ='bold'
        )
        )

        
        fig1.update_traces(marker_line_width=2,marker_line_color='black')
        
        fig1.update_traces(insidetextanchor= 'middle')
        fig1.update_layout(
            uniformtext_minsize=12,
            uniformtext_mode='hide'
            )
        
        fig1.update_layout(margin=dict(t=120, b=90, l=170, r=40))
        
        apply_logo_to_fig(fig1,xval=.4,yval = -0.04)
        self.UpdateColors(fig1)
        
        return fig1
        
   
    
    def PointsOverTheWeekend(self, Alternate=None):    
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
        
        apply_logo_to_fig(figWeekLine,xval=0,yval = 1.06)
        
        return figWeekLine
        
    
    