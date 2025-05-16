import os
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import base64
import io
import time

# Create the Dash app
dash_app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css'
], suppress_callback_exceptions=True)

server = dash_app.server
app = server

dash_app.layout = html.Div(style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh'}, children=[
    dbc.Navbar(
        children=[
            html.A(
                dbc.Row(
                    [
                        dbc.Col(html.I(className="fas fa-chart-line fa-2x", style={'color': 'white'})),
                        dbc.Col(dbc.NavbarBrand("Profesyonel Analiz Paneli", className="ml-2", style={'color': 'white'})),
                    ],
                    align="center",
                    className="g-0",
                ),
                style={'textDecoration': 'none'},
            )
        ],
        color="primary",
        dark=True,
        sticky='top',
        className='mb-4'
    ),

    dbc.Container([
        dbc.Row([
            # SOL SÜTUN (Tüm bileşenler korundu)
            dbc.Col(width=3, children=[
                # DOSYA YÜKLEME KARTI
                dbc.Card(className='shadow mb-4', children=[
                    dbc.CardBody([
                        html.H4("Veri Yükleme", className='text-primary mb-4'),
                        html.Div(id='file-info', className='mt-3'),
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                html.Div([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x text-secondary mb-3"),
                                    html.P("Dosya Sürükle & Bırak", className='lead mb-1'),
                                    html.Small("veya tıklayarak seç", className='text-muted')
                                ], style={'textAlign': 'center'})
                            ]),
                            style={
                                'border': '2px dashed #5A8DB8',
                                'borderRadius': '10px',
                                'padding': '20px',
                                'background': '#E6F1F8',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id='upload-progress', className='mt-3', children=[
                            dbc.Progress(id="progress-bar", value=0, striped=True, animated=True),
                            html.Div(id='progress-percentage',
                                     className='mt-2 text-center h4 text-primary',
                                     style={'fontWeight': 'bold'})
                        ])
                    ])
                ]),

                # İŞLEMLER KARTI (Düzeltilmiş ID'ler)
                dbc.Card(className='shadow mb-4', children=[
                    dbc.CardBody([
                        html.H4("İşlemler", className='text-primary mb-4'),
                        dbc.Form([
                            dbc.Label("Seçenekler:", className='mb-2'),
                            dcc.Checklist(
                                id='islemler-checklist-unique',  # Benzersiz ID
                                options=[
                                    {'label': ' Deneme 1', 'value': 'deneme1'},
                                    {'label': ' Deneme 2', 'value': 'deneme2'}
                                ],
                                labelStyle={'display': 'block'},
                                className='mb-3'
                            ),
                            dcc.Dropdown(
                                id='islemler-dropdown-unique',  # Benzersiz ID
                                options=[
                                    {'label': 'Deneme 1', 'value': 'deneme1'},
                                    {'label': 'Deneme 2', 'value': 'deneme2'}
                                ],
                                placeholder="Seçim Yapın...",
                                className='mb-3'
                            ),
                            dbc.Button(
                                "Test Yap",
                                id='test-buton',
                                color="success",
                                className='mt-3 w-100',
                                n_clicks=0
                            )
                        ])
                    ])
                ])
            ]),

            # SAĞ SÜTUN
            dbc.Col(width=9, children=[
                dbc.Row([dbc.Col(dcc.Graph(id='main-chart'))], className='mb-4'),
                dbc.Row([
                    dbc.Col(dcc.Graph(id='secondary-chart1')),
                    dbc.Col(dcc.Graph(id='secondary-chart2'))
                ]),
                dbc.Row([dbc.Col(dcc.Graph(id='test-chart'))], className='mt-4')
            ])
        ])
    ], fluid=True),

    dcc.Interval(id='progress-interval', interval=100, n_intervals=0),
    dcc.Store(id='stored-data'),
    dcc.Store(id='upload-status', data={'uploading': False})
])

# CALLBACK'LER (Öncekiyle aynı, sadece ID'ler güncellendi)
@dash_app.callback(
    Output('test-chart', 'figure'),
    [Input('test-buton', 'n_clicks')],
    [State('stored-data', 'data')]
)
def generate_test_chart(n_clicks, data):
    if n_clicks == 0 or data is None:
        return dash.no_update

    try:
        df = pd.read_json(data, orient='split')

        if len(df.columns) < 2:
            raise ValueError("En az 2 sütun gereklidir")

        fig = px.scatter(
            df,
            x=df.columns[0],
            y=df.columns[1],
            title=f"Test Grafiği (Tıklanma: {n_clicks})",
            labels={
                df.columns[0]: "X Ekseni",
                df.columns[1]: "Y Ekseni"
            },
            template='plotly_white'
        )
        fig.update_layout(
            plot_bgcolor='rgba(245,245,245,1)',
            paper_bgcolor='rgba(255,255,255,0.8)'
        )
        return fig

    except Exception as e:
        return px.scatter(title=f"Hata: {str(e)}")

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
            return 100, "✔️", html.Span("Yükleme Tamamlandı!", style={'color': 'green'}), status
        return progress, f"%{progress}", f"{progress}%", status

    return 0, "", "", status


@dash_app.callback(
    [Output('stored-data', 'data'), Output('file-info', 'children')],
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
        else:
            return None, dbc.Alert("Geçersiz dosya formatı!", color="danger")
    except Exception as e:
        return None, dbc.Alert(f"Hata: {str(e)}", color="danger")
    file_info = dbc.Card([
        dbc.CardBody([
            dbc.Row([dbc.Col(html.Div([
                html.H5(f"{filename}", className='text-success mb-3'),
                dbc.Badge(f"{df.shape[0]} Satır", color="primary", className='mr-2'),
                dbc.Badge(f"{df.shape[1]} Sütun", color="primary")
            ], className='text-center'))])
        ])
    ], className='shadow-sm')
    return df.to_json(date_format='iso', orient='split'), file_info


@dash_app.callback(
    [Output('main-chart', 'figure'),
     Output('secondary-chart1', 'figure'),
     Output('secondary-chart2', 'figure')],
    [Input('stored-data', 'data')]
)
def update_charts(data):
    if data is None:
        return [px.scatter(), px.bar(), px.pie()]
    df = pd.read_json(io.StringIO(data), orient='split')
    main_chart = px.line(df, template='plotly_white')
    main_chart.update_layout(
        plot_bgcolor='rgba(255,255,255,0.9)',
        paper_bgcolor='rgba(255,255,255,0.5)',
        font_color='#2A5C8D',
        title='Ana Veri Görünümü'
    )
    chart1 = px.bar(df, barmode='group', color_discrete_sequence=['#2A5C8D', '#5A8DB8'])
    chart1.update_layout(title='Sütun Dağılımı')
    chart2 = px.pie(df, names=df.columns[0], hole=0.4)
    chart2.update_layout(title='Kategorik Dağılım')
    return main_chart, chart1, chart2

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8051))
    server.run(host="0.0.0.0", port=port, debug=True)

# Deploy with:
# gunicorn app:app
