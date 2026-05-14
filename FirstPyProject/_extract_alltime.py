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
        self.teamcolors = {'JTizzzzle': 'lightsalmon', 'bgmaddox':'mediumpurple', 'jlglover':'cyan', 'RascalHazard':'pink', 
                    'BMoreBallers88':'gold', 'eegrady':'teal', 'DirtyCommie':'lime', 'jhuntmadd':'orange', 'RReclam':'green', 
                    'sgmaddox':'darkseagreen', 'RossLikeSauce':'red', 'InfiniteJesse':'magenta'}
        if color_dict != None:
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
        
        self.TopPlayerScores = self.Breakout.sort_values('points', ascending=False)[:10]
        self.TopPlayerScores['Names'] = self.TopPlayerScores.team + ' [W' + self.TopPlayerScores.week_x.astype(str) + ' ' + self.TopPlayerScores.year.astype(str)+ ']' + ' - ' + self.TopPlayerScores.points.round(1).astype(str) 
        self.TopPlayerScores['Year'] = self.TopPlayerScores['year'].astype(int)

        self.BottomPlayerScores = self.Breakout.sort_values('points', ascending=True)[:10]
        self.BottomPlayerScores['Names'] = self.BottomPlayerScores.team + ' [W' + self.BottomPlayerScores.week_x.astype(str) + ' ' + self.BottomPlayerScores.year.astype(str)+ ']' + ' - ' + self.BottomPlayerScores.points.round(1).astype(str) 
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
        
        Losers = self.Matches[self.Matches['Won'] == 0]
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
            textfont=dict(size=25)
        ))
        figLosers.add_trace(go.Bar(
            x = TopTenLosers['Opp'],
            y = TopTenLosers['TeamName'],
            name = 'Winners',
            orientation='h',
            opacity=.7,
            text = TopTenLosers['OppName'],
            textfont=dict(size=14),
            ))
        figLosers.update_layout(template="gridiron_ink")
        figLosers.update_layout(width=800, height=1200)
        figLosers.update_layout(showlegend=False)
        figLosers.update_yaxes(
                tickfont=dict(
                    size=18,         # Font size
                ),
                title = None,
            )
        figLosers.update_layout(
            title = "<b>Biggest Losers</b><br><sup>Highest Scores in Loss</sup>",
        )
        figLosers.update_layout(margin=dict(t=130, b=100, l=200, r=40))
        apply_logo_to_fig(figLosers, xval=.35)


        return figLosers
        
    def SmallestMargins(self):
        TenSmallestMargins = self.Matches.sort_values('Abs Margin', ascending=True)[:20]
        TenSmallestMargins = TenSmallestMargins.sort_values('Margin').reset_index()
        TenSmallestMargins['TeamGraph'] = TenSmallestMargins['Team'] + ' - ' + TenSmallestMargins['Year'].astype(str) + ' [' + TenSmallestMargins['Margin'].astype(str) + ']'
        
    
        figMargin = px.bar(TenSmallestMargins, x='Margin',y=TenSmallestMargins.index,template = 'gridiron_ink',title='<b>Top 10 Smallest Margins</b>', color = 'Week Index', orientation='h', text='TeamGraph' )
        figMargin.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'})
        figMargin.update_layout(width=1200, height=800)
        
        figMargin.update_traces(textfont_size=20, textangle=0, cliponaxis=True, textposition = 'auto', textfont=dict(weight='bold', size=15   # Font color
                ))
        figMargin.update_layout(
                xaxis_title="Margin",  # Set x-axis title
                yaxis_title="",   # Set y-axis title
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
        
        
        
        figWorst = px.bar(Worst10, x='Total',y='TeamName', color = 'Team', orientation='h', template='gridiron_ink', title = '<b>Hall of Shame</b><br><sup>Team</sup>', text = 'Total')
        figWorst.update_layout(height = 1200, width= 800, showlegend=False)
        figWorst.update_layout(title_font = dict(size=45))
        figWorst.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
            )
        figWorst.update_yaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                categoryorder="total descending",
            )

        # Add the image over a specific bar (adjust xref and yref as needed for placement)
        figWorst.update_traces(textposition='inside', textfont_size=80)
        figWorst.update_layout(margin=dict(t=130, b=100, l=200, r=40))
        
        apply_logo_to_fig(figWorst,xval=.40)

        return figWorst
    
    def HallofFame_Team(self):
        Best10 = self.Matches.sort_values('Total', ascending=False)[0:10]
        Best10['Total'] = Best10['Total'].astype(int)
        Best10['TeamName'] = '<b>'+ Best10['Team'] + '</b>' + '<br>' + "W" +Best10['Week'].astype(str) + " " + Best10['Year'].astype(str)
        
        figBest = px.bar(Best10, x='Total',y='TeamName', color = 'Team', orientation='h', template='gridiron_ink', title = '<b>Hall of Fame</b><br><sup>Team</sup>', text = 'Total')
        figBest.update_layout(height = 1200, width= 800, showlegend=False)
        figBest.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                
            )
        figBest.update_yaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                categoryorder="total ascending",
            )
        figBest.update_layout(
            font=dict(
                size=20,  # Set the font size here
            )
        )
        figBest.update_layout(margin=dict(t=130, b=100, l=180, r=40))
        figBest.update_traces(textposition='inside', textfont_size=80)

        
        apply_logo_to_fig(figBest,xval=.40)
        return figBest
        
    def HallofFame_Player(self):
            
        Best10Players = self.Breakout.sort_values('points', ascending=False)[0:10]
        Best10Players['TeamName'] = '<b>' + Best10Players['team'] + '</b><br><sup>' + "W" +Best10Players['week_x'].astype(str) + " " + Best10Players['year'].astype(str) + '</sup>'
        Best10Players['Player-Points'] = '<b>' + Best10Players.player + '</b><br>' + Best10Players.points.astype(str)
        
        figBestPlayers = px.bar(Best10Players, x='points',y='TeamName', color = 'team', orientation='h', 
                        template='gridiron_ink', title = '<b>Hall of Fame</b><br><sup>Players</sup>', text = 'Player-Points',
                        )
        figBestPlayers.update_layout(height = 1200, width= 800, showlegend=False)
        figBestPlayers.update_xaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                
            )
        figBestPlayers.update_yaxes(
                tickfont=dict(
                    size=16,         # Font size
                ),
                title = None,
                categoryorder="total ascending",
            )
        
        figBestPlayers.update_layout(margin=dict(t=130, b=100, l=180, r=40))
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
    
        #TeamPointsTOP['color'] = TeamPointsTOP.team.map(teamcolors)
        TeamPointsTOP['TeamVs'] = TeamPointsTOP.team + ' w/ ' + TeamPointsTOP.recent_teams
        TeamPointsTOP['Purpose'] = 'Points With...'
        
        JointTopBottom = pd.concat([OpponentPointsNoTeamTOP,TeamPointsTOP ])
        
        figTeamPoints = go.Figure()

        figTeamPoints = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=False,
                    vertical_spacing =  .1,
                    #column_widths=[0.5, 0.55],  # Adjust the width of each subplot
                    specs=[[{"type": "bar"}],
                            [{"type": "bar"}]],
                    subplot_titles=['Points With...','Points vs...']# Specify the chart types
                )
        figTeamPoints.add_trace(
                    go.Bar(
                        x=TeamPointsTOP['points'], 
                        y=TeamPointsTOP['TeamVs'], 
                        
                        text=TeamPointsTOP['points'],
                        textangle = 0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h', 
                        marker_color = TeamPointsTOP.points,
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
                        textangle = 0,
                        textposition='auto',
                        showlegend=False,
                        orientation='h',
                        marker_color = OpponentPointsNoTeamTOP.points,
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

        figTeamPoints.update_layout(margin=dict(t=100, b=100, l=220, r=40))
        
        apply_logo_to_fig(figTeamPoints,xval=.40, yval=-0.06)


        return figTeamPoints
            
    
       
        
        
        