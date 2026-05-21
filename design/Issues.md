# This Week

1. ✅ "Matchups" graph: the "vs" on the bottom two pairs is too low. It's okay on the top 4 pairs. We should bump up those annotations just a little to try and center them.

2. ✅ Lineup Efficiency: The font for the y-axis is a bit small. Can we review all of our horizontal bar graphs within the app and standardize the font size for them across the board so all of the horizontal bar chart y-axis labels look the same?

# Season

1. ✅ "Points for and against" graph: the y-axis label font is too small. Same as with #2 above, let's standardize these font sizes so it's both consistent and readable. There is plenty of space here so no need to have such small font.

2. ✅ Weekly Wins: Currently the dtick value for the x-axis is set to 3. Should we change that? Should we change the d-tick for the y-axis too? Again, readablility, consistency, and stylishness are the goals here.

3. ✅ Score map race, heatmap, and draft board replay are currently not displaying. Just empty containers there. Fixed by adding boot.disabled as a callback input so stores re-populate after data finishes loading.

# Player

1. ✅ "Player Points": Same issue as #2 above about d-tick values. Should we change these? Should we make our d-tick values for our graphs the same accross the app to have a more consistent look?

2. ✅ "Scoring Distribution": Currently displays an error in the container. Says "No data for this week range" despite the fact there should be. Fixed by filtering on the correct week_x column.

3. ✅ Top Players: The new point toggle design was a good attempt but I still don't like the styling of it. Can we just have a box that blends in well with the rest of the graph, that a user can enter their point threshold value?

# All-time

1. ✅ These y-axis labels are a bit more involved, but are we able to take the part of the y-axis label that has the team name and make the font color match the assigned color for our app? Implemented via per-bar annotations with team color replacing tick labels on HallofFame, HallofShame, and HighestScoringLosers.

2. ✅ "Highest Scoring Losses": This graph is displaying very strangely. Whole bars seem to be missing, mostly the top bar in the pairs. Fixed by filtering out rows with NaN Opp_team and regenerating stale caches.

3. ✅ All time points for and against: top axis label is clipped by the container. Y-axis labels of team names are being clipped. More room needed for both. Margins increased.

4. ✅ All the graphs below "All time points for and against" are not displaying. Fixed: NameError in chord data callback (all_owners undefined) caused silent failures; also fixed prevent_initial_call blocking clientside callbacks and added _ts timestamps to force store updates on repeat tab visits.
