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
    paper_bgcolor=ink_bg_color,
    plot_bgcolor=ink_bg_color,
    barmode = 'group',
    # --- Fonts ---
    font_family=ink_font,
    font_color=ink_text_color,
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
    width = 1200,
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
        bgcolor='rgba(0,0,0,0)', # Transparent legend background
        bordercolor=ink_grid_color,
        borderwidth=1,
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


# --- Example Usage ---
# Now, any chart you create will automatically use your new theme!
fig = go.Figure(data=[
    go.Bar(name='Team A', x=['Week 1', 'Week 2', 'Week 3'], y=[110, 145, 95]),
    go.Bar(name='Team B', x=['Week 1', 'Week 2', 'Week 3'], y=[125, 105, 150])
])

fig.update_layout(
    title_text='Weekly Fantasy Scores',
    xaxis_title='Week',
    yaxis_title='Points'
)


apply_logo_to_fig(fig)


fig.show()