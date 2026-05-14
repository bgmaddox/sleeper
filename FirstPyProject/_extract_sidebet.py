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
        Members = self.Season.Matches.Team.unique()
        self.teamcolors = dict(zip(Members,coastal_colorway))
        
        
        if color_dict != None:
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
            
            figSideBets.update_layout(width=1200, height=1200, title_text = '<b>Side Bet Tally</b>')

            apply_logo_to_fig(figSideBets)
            figSideBets.update_layout(title ={'y':.93, 'font':dict(size=65)})
            self.Tally = tallyDF
            return figSideBets
        
    
    
    def Week1(self, WeekObj,top):
        
        df = WeekObj.WeeklyNoMatches
        df = df.sort_values('Total', ascending = False)
        top = df['Team'][0]
        
        #points = df.drop(axis = 1,columns = ['Total','Won','Week','Opp','Matchup']).applymap(lambda x: float(list(x.values())[0]))
        points = df.applymap(lambda x: float(list(x.values())[0]) if isinstance(x, dict) else x)
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

        fig1.update_traces(marker_line_width=1.5,marker_line_color='black')
        
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
        fig.update_traces(marker_line_width=2,marker_line_color='black')
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
        figWeek5.update_layout(width=1200, height=800, showlegend = True)
        
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
        points = df.drop(axis = 1,columns = ['Total','Won','Week','Opp','Matchup']).applymap(lambda x: float(list(x.values())[0]))
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
        

        figQBComplete.update_traces(marker_line_width=1.5,marker_line_color='black')

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
        figWeek13.update_layout(width=1200, height=800)

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


                        
