import os
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import io
import time
from lib.rpc import ReadRPC
import tempfile


from lib.calculations import TimeToRpmCsv, RpmToTimeCsv

# Create the Dash app
dash_app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
], suppress_callback_exceptions=True)

server = dash_app.server
app = server

# Modern CSS styles
modern_styles = {
    'main_container': {
        'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'minHeight': '100vh',
        'fontFamily': 'Inter, sans-serif'
    },
    'navbar_style': {
        'background': 'rgba(255, 255, 255, 0.95)',
        'backdropFilter': 'blur(10px)',
        'border': 'none',
        'boxShadow': '0 8px 32px rgba(0, 0, 0, 0.1)',
        'borderRadius': '0 0 20px 20px',
        'margin': '0 20px'
    },
    'card_style': {
        'background': 'rgba(255, 255, 255, 0.95)',
        'backdropFilter': 'blur(10px)',
        'border': 'none',
        'borderRadius': '20px',
        'boxShadow': '0 10px 40px rgba(0, 0, 0, 0.1)',
        'border': '1px solid rgba(255, 255, 255, 0.2)',
        'transition': 'all 0.3s ease'
    },
    'upload_area': {
        'border': '3px dashed rgba(102, 126, 234, 0.4)',
        'borderRadius': '20px',
        'padding': '30px',
        'background': 'linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1))',
        'cursor': 'pointer',
        'transition': 'all 0.3s ease',
        'textAlign': 'center'
    },
    'button_primary': {
        'background': 'linear-gradient(135deg, #667eea, #764ba2)',
        'border': 'none',
        'borderRadius': '12px',
        'padding': '12px 24px',
        'fontWeight': '600',
        'color': 'white',
        'transition': 'all 0.3s ease',
        'boxShadow': '0 4px 15px rgba(102, 126, 234, 0.3)'
    },
    'input_style': {
        'borderRadius': '12px',
        'border': '2px solid rgba(102, 126, 234, 0.2)',
        'padding': '12px 16px',
        'fontSize': '14px',
        'transition': 'all 0.3s ease',
        'background': 'rgba(255, 255, 255, 0.9)'
    }
}

dash_app.layout = html.Div(style=modern_styles['main_container'], children=[
    # Modern Navbar
    html.Div(style={'padding': '20px 0 30px 0'}, children=[
        dbc.Card(style=modern_styles['navbar_style'], children=[
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.I(className="fas fa-chart-line",
                                   style={'fontSize': '32px', 'color': '#667eea', 'marginRight': '15px'}),
                            html.H2("Profesyonel Analiz Paneli",
                                    style={'color': '#2d3748', 'fontWeight': '700', 'margin': '0',
                                           'display': 'inline-block'})
                        ], style={'display': 'flex', 'alignItems': 'center'})
                    ], width=8),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-database", style={'color': '#667eea', 'fontSize': '20px'}),
                                html.Span("Veri Analiz", style={'marginLeft': '8px', 'fontWeight': '500'})
                            ], style={'background': 'rgba(102, 126, 234, 0.1)', 'padding': '8px 16px',
                                      'borderRadius': '20px', 'display': 'inline-flex', 'alignItems': 'center'})
                        ], style={'textAlign': 'right'})
                    ], width=4)
                ], align="center")
            ])
        ])
    ]),

    dbc.Container([
        dbc.Row([
            # SOL SÜTUN - Modern Control Panel
            dbc.Col(width=3, children=[
                # File Upload Card
                dbc.Card(style=modern_styles['card_style'], className='mb-4', children=[
                    dbc.CardBody([
                        # Upload header
                        html.Div([
                            html.I(className="fas fa-cloud-upload-alt",
                                   style={'fontSize': '24px', 'color': '#667eea', 'marginRight': '10px'}),
                            html.H4("Veri Yükleme", style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                           'display': 'inline-block'})
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'}),

                        # ---- NEW: file-info placeholder ----
                        html.Div(id='file-info', className='mt-3'),

                        # ---- NEW: actual upload area ----
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                html.Div([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x text-secondary mb-3"),
                                    html.P("Dosya Sürükle & Bırak", className='lead mb-1'),
                                    html.Small("veya tıklayarak seç", className='text-muted')
                                ], style={'textAlign': 'center'})
                            ]),
                            style=modern_styles['upload_area'],
                            multiple=False
                        ),

                        # ---- NEW: progress bar + percentage ----
                        html.Div(id='upload-progress', className='mt-4', children=[
                            dbc.Progress(
                                [
                                    dbc.Progress(
                                        value=0,
                                        striped=True,
                                        animated=True,
                                        style={'height': '12px', 'borderRadius': '10px',
                                               'background': 'linear-gradient(135deg, #667eea, #764ba2)'},
                                        bar=True
                                    )
                                ],
                                id="progress-bar",
                                style={'height': '12px', 'borderRadius': '10px',
                                       'background': 'rgba(102, 126, 234, 0.1)'}
                            ),
                            html.Div(
                                id='progress-percentage',
                                className='mt-2 text-center',
                                style={'fontWeight': '600', 'color': '#667eea', 'fontSize': '18px'}
                            )
                        ])
                    ])
                ]),

                # Operations Card
                dbc.Card(style=modern_styles['card_style'], children=[
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-cogs",
                                   style={'fontSize': '24px', 'color': '#667eea', 'marginRight': '10px'}),
                            html.H4("İşlemler", style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                       'display': 'inline-block'})
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '25px'}),

                        dbc.Form([
                            # Overall Selection
                            html.Div([
                                dbc.Label("Overall",
                                          style={'fontWeight': '600', 'color': '#4a5568', 'marginBottom': '10px'}),
                                html.Div([
                                    dcc.RadioItems(
                                        id='overall-selection',
                                        options=[
                                            {'label': html.Div([
                                                html.I(className="fas fa-clock",
                                                       style={'marginRight': '8px', 'color': '#667eea'}),
                                                'overallVsTime'
                                            ], style={'display': 'flex', 'alignItems': 'center', 'padding': '8px 12px',
                                                      'border': '2px solid rgba(102, 126, 234, 0.2)',
                                                      'borderRadius': '10px',
                                                      'marginBottom': '8px', 'transition': 'all 0.3s ease'}),
                                                'value': 'overallVsTime'},
                                            {'label': html.Div([
                                                html.I(className="fas fa-tachometer-alt",
                                                       style={'marginRight': '8px', 'color': '#667eea'}),
                                                'overallVsrpm'
                                            ], style={'display': 'flex', 'alignItems': 'center', 'padding': '8px 12px',
                                                      'border': '2px solid rgba(102, 126, 234, 0.2)',
                                                      'borderRadius': '10px',
                                                      'transition': 'all 0.3s ease'}), 'value': 'overallVsrpm'}
                                        ],
                                        value='overallVsTime',
                                        labelStyle={'display': 'block', 'margin': '0'},
                                        className='mb-3'
                                    )
                                ])
                            ], className='mb-4'),

                            # Options
                            html.Div([
                                dbc.Label("Seçenekler",
                                          style={'fontWeight': '600', 'color': '#4a5568', 'marginBottom': '10px'}),
                                dcc.Checklist(
                                    id='islemler-checklist-unique',
                                    options=[
                                        {'label': html.Div([
                                            html.I(className="fas fa-signal",
                                                   style={'marginRight': '8px', 'color': '#48bb78'}),
                                            'A-weighting'
                                        ], style={'display': 'flex', 'alignItems': 'center', 'padding': '8px 12px',
                                                  'border': '2px solid rgba(72, 187, 120, 0.2)', 'borderRadius': '10px',
                                                  'transition': 'all 0.3s ease'}), 'value': 'a_weighting'}
                                    ],
                                    labelStyle={'display': 'block', 'margin': '0'},
                                    className='mb-4'
                                )
                            ]),

                            # Parameters
                            html.Div([
                                dbc.Label("Parametreler",
                                          style={'fontWeight': '600', 'color': '#4a5568', 'marginBottom': '15px'}),
                                html.Div([
                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-arrow-up"),
                                                           style={'background': 'rgba(102, 126, 234, 0.1)',
                                                                  'border': 'none'}),
                                        dbc.Input(id='maxRpm', placeholder='maxRpm', type='number',
                                                  style=modern_styles['input_style'])
                                    ], className='mb-3'),

                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-arrow-down"),
                                                           style={'background': 'rgba(102, 126, 234, 0.1)',
                                                                  'border': 'none'}),
                                        dbc.Input(id='minRpm', placeholder='minRpm', type='number',
                                                  style=modern_styles['input_style'])
                                    ], className='mb-3'),

                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-plus"),
                                                           style={'background': 'rgba(102, 126, 234, 0.1)',
                                                                  'border': 'none'}),
                                        dbc.Input(id='increment', placeholder='increment', type='number',
                                                  style=modern_styles['input_style'])
                                    ], className='mb-4')
                                ])
                            ]),

                            # Action Button
                            html.Div([
                                dbc.Button([
                                    html.I(className="fas fa-play", style={'marginRight': '8px'}),
                                    "Test Yap"
                                ], id='test-buton',
                                    style=modern_styles['button_primary'],
                                    className='w-100',
                                    size='lg',
                                    n_clicks=0)
                            ])
                        ])
                    ])
                ])
            ]),

            # SAĞ SÜTUN - Modern Charts
            dbc.Col(width=9, children=[
                # Main Chart
                dbc.Row([
                    dbc.Col([
                        dbc.Card(style=modern_styles['card_style'], children=[
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-chart-area",
                                           style={'fontSize': '20px', 'color': '#667eea', 'marginRight': '10px'}),
                                    html.H5("Ana Veri Görünümü",
                                            style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                   'display': 'inline-block'})
                                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'}),
                                dcc.Graph(id='main-chart', style={'height': '400px'})
                            ])
                        ])
                    ])
                ], className='mb-4'),

                # Secondary Charts
                dbc.Row([
                    dbc.Col([
                        dbc.Card(style=modern_styles['card_style'], children=[
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-chart-bar",
                                           style={'fontSize': '18px', 'color': '#48bb78', 'marginRight': '8px'}),
                                    html.H6("Sütun Dağılımı",
                                            style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                   'display': 'inline-block'})
                                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px'}),
                                dcc.Graph(id='secondary-chart1', style={'height': '300px'})
                            ])
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Card(style=modern_styles['card_style'], children=[
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-chart-pie",
                                           style={'fontSize': '18px', 'color': '#ed8936', 'marginRight': '8px'}),
                                    html.H6("Kategorik Dağılım",
                                            style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                   'display': 'inline-block'})
                                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px'}),
                                dcc.Graph(id='secondary-chart2', style={'height': '300px'})
                            ])
                        ])
                    ], width=6)
                ]),

                # Test Chart
                dbc.Row([
                    dbc.Col([
                        dbc.Card(style=modern_styles['card_style'], children=[
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-flask",
                                           style={'fontSize': '20px', 'color': '#9f7aea', 'marginRight': '10px'}),
                                    html.H5("Test Grafiği",
                                            style={'color': '#2d3748', 'fontWeight': '600', 'margin': '0',
                                                   'display': 'inline-block'})
                                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'}),
                                dcc.Graph(id='test-chart', style={'height': '400px'})
                            ])
                        ])
                    ])
                ], className='mt-4')
            ])
        ])
    ], fluid=True),

    dcc.Interval(id='progress-interval', interval=100, n_intervals=0),
    dcc.Store(id='stored-data', storage_type='memory'),
    dcc.Store(id='upload-status',storage_type='memory', data={'uploading': False})
])


@dash_app.callback(
    Output('test-chart', 'figure'),
    [Input('test-buton', 'n_clicks')],
    [
        State('stored-data', 'data'),
        State('islemler-checklist-unique', 'value'),
        State('maxRpm', 'value'),
        State('minRpm', 'value'),
        State('increment', 'value'),
        State('overall-selection', 'value')
    ]
)
def generate_test_chart(n_clicks, data, checklist_values, max_rpm, min_rpm, increment, overall_selection):
    if n_clicks == 0 or data is None:
        # Create empty modern chart
        fig = go.Figure()
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568'),
            title=dict(text="Test verilerini görmek için 'Test Yap' butonuna basın",
                       font=dict(size=16, color='#718096')),
            xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
        )
        return fig

    try:
        df = pd.read_json(io.StringIO(data), orient='split')

        # Kullanıcının yüklediği dosyadan s, rpm, pa değerlerini al
        time_values = df['s'].values  # Zaman değerleri
        rpm_values = df['rpm'].values  # RPM değerleri
        pa_values = df['pa'].values  # Basınç değerleri

        # Set default values if not provided
        if max_rpm is None:
            max_rpm = df['rpm'].max() if 'rpm' in df.columns else 6000
        if min_rpm is None:
            min_rpm = df['rpm'].min() if 'rpm' in df.columns else 1000
        if increment is None:
            increment = 25

        # Check if A-weighting is selected
        apply_a_weighting = checklist_values and 'a_weighting' in checklist_values

        # Perform calculations based on selection
        if overall_selection == 'overallVsTime':
            # Time to RPM calculation
            if apply_a_weighting:
                fs, weighted_pa = RpmToTimeCsv.calculate_sample_rate(time_values, pa_values)
                n_blocks = int((max_rpm - min_rpm)/increment) + 1
                result_data = TimeToRpmCsv.analyze_time_series(time_values, rpm_values, time_values, weighted_pa, n_blocks )

            else:
                n_blocks = int((max_rpm - min_rpm) / increment) + 1
                result_data = TimeToRpmCsv.analyze_time_series(time_values, rpm_values, time_values, pa_values, n_blocks )

            # Verinin 1. sütununu x, 2. sütununu y ekseni olarak kullan
            x_column = result_data.columns[0]  # İlk sütun
            y_column = result_data.columns[1]  # İkinci sütun

            # Create time vs overall chart
            fig = px.line(result_data, x=x_column, y=y_column,
                          title=f'Overall vs Time Analysis (RPM: {min_rpm}-{max_rpm}, Inc: {increment})')

            # Add RPM color mapping if available
            if 'rpm' in result_data.columns:
                fig = px.scatter(result_data, x=x_column, y=y_column, color='rpm',
                                 title=f'Overall vs Time Analysis (RPM: {min_rpm}-{max_rpm}, Inc: {increment})',
                                 color_continuous_scale='Viridis')

            fig.update_traces(line=dict(width=3))
            fig.update_xaxes(title_text=x_column)
            fig.update_yaxes(title_text=y_column)

        elif overall_selection == 'overallVsrpm':
            # RPM to Time calculation
            if apply_a_weighting:
                fs, weighted_pa = RpmToTimeCsv.calculate_sample_rate(time_values, pa_values)
                result_data = RpmToTimeCsv.process_rpm_data(rpm_values, time_values, weighted_pa, increment)
            else:
                result_data = RpmToTimeCsv.process_rpm_data(rpm_values, time_values, pa_values, increment)

            # Create RPM vs overall chart
            fig = px.line(result_data, x='rpm', y='overall',
                          title=f'Overall vs RPM Analysis (RPM: {min_rpm}-{max_rpm}, Inc: {increment})')

            # Add time color mapping if available
            if 'time' in result_data.columns:
                fig = px.scatter(result_data, x='rpm', y='overall', color='time',
                                 title=f'Overall vs RPM Analysis (RPM: {min_rpm}-{max_rpm}, Inc: {increment})',
                                 color_continuous_scale='Plasma')

            fig.update_traces(line=dict(width=3))
            fig.update_xaxes(title_text="RPM")
            fig.update_yaxes(title_text="Overall Level (dB)")

        # Apply modern styling
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568'),
            title=dict(font=dict(size=18, color='#2d3748')),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(102, 126, 234, 0.1)',
                linecolor='rgba(102, 126, 234, 0.3)'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(102, 126, 234, 0.1)',
                linecolor='rgba(102, 126, 234, 0.3)'
            ),
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="rgba(102, 126, 234, 0.5)",
                font_color="#2d3748"
            )
        )

        # Add annotation with parameters
        a_weight_text = " (A-weighted)" if apply_a_weighting else ""
        fig.add_annotation(
            text=f"Parameters: Max RPM: {max_rpm}, Min RPM: {min_rpm}, Increment: {increment}{a_weight_text}",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=12, color='#718096'),
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="rgba(102, 126, 234, 0.3)",
            borderwidth=1,
            borderpad=4
        )

        return fig

    except Exception as e:
        # Error handling with modern styling
        fig = go.Figure()
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568'),
            title=dict(text=f"Hata: {str(e)}", font=dict(size=16, color='#e53e3e')),
            xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
        )

        # Add error details as annotation
        fig.add_annotation(
            text="Lütfen gerekli parametreleri kontrol edin ve tekrar deneyin.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color='#e53e3e'),
            bgcolor="rgba(229, 62, 62, 0.1)",
            bordercolor="rgba(229, 62, 62, 0.3)",
            borderwidth=1,
            borderpad=10
        )

        return fig


@dash_app.callback(
    [Output('progress-bar', 'value'),
     Output('progress-bar', 'label'),
     Output('progress-percentage', 'children'),
     Output('upload-status', 'data')],
    [Input('upload-data', 'contents'),
     Input('progress-interval', 'n_intervals')],
    [State('upload-status', 'data'),
     State('upload-data', 'filename')]
)
def update_progress(contents, n_intervals, status, filename):
    ctx = dash.callback_context
    if not ctx.triggered:
        return 0, "", "", dash.no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'upload-data' and contents:
        status = {'uploading': True, 'start_time': time.time()}
        return 0, "", "", status
    elif status.get('uploading'):
        elapsed = time.time() - status['start_time']
        progress = min(100, int((elapsed / 3) * 100))
        if progress >= 100:
            status['uploading'] = False
            return 100, "✔️", html.Div([
                html.I(className="fas fa-check-circle", style={'color': '#48bb78', 'marginRight': '8px'}),
                "Yükleme Tamamlandı!"
            ], style={'color': '#48bb78', 'fontWeight': '600'}), status
        return progress, f"%{progress}", f"{progress}%", status
    return 0, "", "", status


@dash_app.callback(
    [Output('stored-data', 'data'),
     Output('file-info', 'children')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def process_data(contents, filename):
    if contents is None:
        return None, None

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))

        elif 'xls' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))

        elif 'rsp' in filename.lower():
            # base64'ten decode edilmiş dosya içeriği 'decoded' olarak varsayalım
            with tempfile.NamedTemporaryFile(delete=False, suffix='.rsp') as temp_file:
                temp_file.write(decoded)
                temp_file_path = temp_file.name  # Geçici dosyanın tam yolu

            rpc = ReadRPC(temp_file_path)
            rpc.parse()
            df = rpc.to_dataframe()
            # İstenen sütunları seç
            # Sadece gerekli sütunları seç ve isimlendir
            df = df[['Time (s)', 'AI C-16/MidSeatMic', 'CNT A-1/EngRpm']].rename(columns={
                'Time (s)': 's',
                'AI C-16/MidSeatMic': 'pa',
                'CNT A-1/EngRpm': 'rpm'
            })
            # Veri tiplerini optimize et
            df = df.astype({
                's': 'float32',
                'pa': 'float32',
                'rpm': 'float32'
            })

        else:
            raise ValueError("Geçersiz dosya formatı!")

    except Exception as e:
        alert = dbc.Alert([
            html.I(className="fas fa-times-circle", style={'marginRight': '8px'}),
            str(e)
        ], color="danger", style={'borderRadius': '12px'})
        return None, alert

    info_card = dbc.Card(
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-file-excel",
                       style={'fontSize': '24px', 'color': '#48bb78', 'marginBottom': '10px'}),
                html.H6(f"{filename}", style={'color': '#2d3748', 'fontWeight': '600', 'marginBottom': '15px'}),
                html.Div([
                    dbc.Badge([
                        html.I(className="fas fa-list", style={'marginRight': '5px'}),
                        f"{df.shape[0]} Satır"
                    ], color="primary", className='me-2', style={'borderRadius': '15px', 'padding': '8px 12px'}),
                    dbc.Badge([
                        html.I(className="fas fa-columns", style={'marginRight': '5px'}),
                        f"{df.shape[1]} Sütun"
                    ], color="info", style={'borderRadius': '15px', 'padding': '8px 12px'})
                ])
            ], style={'textAlign': 'center'})
        ]),
        style={'background': 'linear-gradient(135deg, rgba(72, 187, 120, 0.1), rgba(56, 178, 172, 0.1))',
               'border': '2px solid rgba(72, 187, 120, 0.2)', 'borderRadius': '15px'}
    )

    return df.to_json(date_format='iso', orient='split'), info_card


@dash_app.callback(
    [Output('main-chart', 'figure'),
     Output('secondary-chart1', 'figure'),
     Output('secondary-chart2', 'figure')],
    [Input('stored-data', 'data')]
)
def update_charts(data):
    if data is None:
        # Create empty modern charts
        empty_main = go.Figure()
        empty_main.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568'),
            title=dict(text="Veri yüklenmeyi bekliyor...", font=dict(size=16, color='#718096')),
            xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
        )

        empty_bar = go.Figure()
        empty_bar.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568'),
            xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
        )

        empty_pie = go.Figure()
        empty_pie.update_layout(
            template='plotly_white',
            plot_bgcolor='rgba(255,255,255,0.1)',
            paper_bgcolor='rgba(255,255,255,0)',
            font=dict(family="Inter", color='#4a5568')
        )

        return empty_main, empty_bar, empty_pie

    df = pd.read_json(io.StringIO(data), orient='split')

    # Modern Main Chart
    main_chart = px.line(df, template='plotly_white')
    main_chart.update_layout(
        plot_bgcolor='rgba(255,255,255,0.1)',
        paper_bgcolor='rgba(255,255,255,0)',
        font=dict(family="Inter", color='#4a5568'),
        xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
    )
    main_chart.update_traces(line=dict(color='#667eea', width=3))

    # Modern Bar Chart
    chart1 = px.bar(df, barmode='group',
                    color_discrete_sequence=['#667eea', '#764ba2', '#48bb78', '#ed8936'])
    chart1.update_layout(
        template='plotly_white',
        plot_bgcolor='rgba(255,255,255,0.1)',
        paper_bgcolor='rgba(255,255,255,0)',
        font=dict(family="Inter", color='#4a5568'),
        xaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(102, 126, 234, 0.1)')
    )

    # Modern Pie Chart
    chart2 = px.pie(df, names=df.columns[0], hole=0.5,
                    color_discrete_sequence=['#667eea', '#764ba2', '#48bb78', '#ed8936', '#9f7aea'])
    chart2.update_layout(
        template='plotly_white',
        plot_bgcolor='rgba(255,255,255,0.1)',
        paper_bgcolor='rgba(255,255,255,0)',
        font=dict(family="Inter", color='#4a5568')
    )

    return main_chart, chart1, chart2


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8051))
    server.run(host="0.0.0.0", port=port, debug=True)