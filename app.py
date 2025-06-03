import dash
from dash import html, dcc, callback_context
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import base64
import io
import time
import pandas as pd
import numpy as np
from lib.rpc import ReadRPC
import tempfile
from dash.exceptions import PreventUpdate
from dash import callback, no_update
import threading
import os

from lib.calculations import TimeToRpmCsv, RpmToTimeCsv

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# Uzun süren işlemler için global değişkenler
analysis_thread = None
analysis_result = None
analysis_running = False
analysis_filename = None

# Modern CSS stilleri
upload_style = {
    'width': '100%',
    'height': '120px',
    'borderWidth': '2px',
    'borderStyle': 'dashed',
    'borderRadius': '10px',
    'borderColor': '#dee2e6',
    'textAlign': 'center',
    'margin': '15px 0',
    'backgroundColor': '#f8f9fa',
    'color': '#6c757d',
    'cursor': 'pointer',
    'display': 'flex',
    'flexDirection': 'column',
    'justifyContent': 'center',
    'alignItems': 'center',
    'transition': 'all 0.3s ease'
}

# Modern panel stilleri
panel_style = {
    'backgroundColor': '#ffffff',
    'border': '1px solid #dee2e6',
    'borderRadius': '8px',
    'height': '85vh',
    'overflow': 'hidden',
    'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
}

panel_content_style = {
    'padding': '16px',
    'height': 'calc(85vh - 50px)',
    'overflowY': 'auto',
    'backgroundColor': '#ffffff'
}

tab_style = {
    'backgroundColor': '#f8f9fa',
    'border': '1px solid #dee2e6',
    'borderBottom': 'none',
    'padding': '8px 16px',
    'margin': '0 2px',
    'borderRadius': '8px 8px 0 0',
    'fontSize': '13px',
    'color': '#495057',
    'cursor': 'pointer'
}

active_tab_style = {
    'backgroundColor': '#ffffff',
    'border': '1px solid #dee2e6',
    'borderBottom': '1px solid #ffffff',
    'padding': '8px 16px',
    'margin': '0 2px',
    'borderRadius': '8px 8px 0 0',
    'fontSize': '13px',
    'color': '#007bff',
    'fontWeight': '600',
    'cursor': 'pointer'
}

app.layout = html.Div([
    # Modern Navbar
    html.Div([
        html.Div([
            html.Span([
                html.I(className="fas fa-chart-line", style={"marginRight": "10px", "fontSize": "20px"}),
                "Pool Project 4"
            ], style={"fontSize": "16px", "fontWeight": "600", "color": "#495057"})
        ], style={"padding": "8px 16px", "backgroundColor": "#f8f9fa", "borderBottom": "1px solid #dee2e6"})
    ]),

    # Ana içerik alanı
    html.Div([
        dbc.Container([
            dbc.Row([
                # Sol Panel - Sources
                dbc.Col([
                    html.Div([
                        # Tab başlıkları
                        html.Div([
                            html.Div("Sources ", style=active_tab_style)
                        ], style={"display": "flex", "marginBottom": "0"}),

                        # Panel içeriği
                        html.Div([
                            # Dosya yükleme alanı
                            html.Div([
                                html.H6("Veri Yükleme",
                                        style={'color': '#495057', 'marginBottom': '10px', 'fontSize': '14px'}),
                                dcc.Upload(
                                    id='upload-data',
                                    children=html.Div([
                                        html.I(className="fas fa-cloud-upload-alt",
                                               style={"fontSize": "32px", "marginBottom": "8px", "color": "#6c757d"}),
                                        html.Div("Dosya Sürükle & Bırak",
                                                 style={"fontSize": "14px", "fontWeight": "500",
                                                        "marginBottom": "4px"}),
                                        html.Div("Veya tıklayarak seç",
                                                 style={"fontSize": "11px", "color": "#868e96"})
                                    ], style={'textAlign': 'center'}),
                                    style=upload_style,
                                    multiple=True,
                                    accept='.csv,.xlsx,.rsp'
                                ),

                                # Progress bar
                                dbc.Progress(
                                    id="upload-progress",
                                    value=0,
                                    striped=True,
                                    animated=False,
                                    color="primary",
                                    style={'display': 'none', 'height': '6px', 'marginBottom': '12px'}
                                ),

                                # Yüklenen dosyalar
                                html.Div(id='uploaded-files-container'),

                                # Header seçim bölümü
                                html.Div(id='header-selection-container', style={'marginTop': '20px'})
                            ])
                        ], style=panel_content_style)
                    ], style=panel_style)
                ], width=3),

                # Orta Panel - Analyses
                dbc.Col([
                    html.Div([
                        # Tab başlıkları
                        html.Div([
                            html.Div("Analyses", style=active_tab_style)
                        ], style={"display": "flex", "marginBottom": "0"}),

                        # Panel içeriği
                        html.Div([
                            # Analiz seçenekleri
                            html.Div([
                                html.H6("Analiz Türü Seçin",
                                        style={'color': '#495057', 'marginBottom': '15px', 'fontSize': '14px'}),

                                # Tek seçimlik radyo buton grubu
                                dbc.RadioItems(
                                    id='analysis-type-radio',
                                    options=[
                                        {"label": "FFT vs Time", "value": "FFTvsTime"},
                                        {"label": "FFT vs Rpm", "value": "FFTvsRpm"},
                                        {"label": "OrderCut", "value": "OrderCut"},
                                    ],
                                    value=None,  # Başlangıçta seçili değil
                                    style={'margin': '10px 0'}
                                )
                            ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'})
                        ], style=panel_content_style)
                    ], style=panel_style)
                ], width=3),

                # Sağ Panel - Destination
                dbc.Col([
                    html.Div([
                        # Tab başlıkları
                        html.Div([
                            html.Div("Destination", style=active_tab_style)
                        ], style={"display": "flex", "marginBottom": "0"}),

                        # Panel içeriği
                        html.Div([
                            html.Div([
                                html.I(className="fas fa-database",
                                       style={"marginRight": "8px", "color": "#17a2b8"}),
                                "Data Viewer"
                            ], style={"padding": "12px", "color": "#6c757d", "textAlign": "center"})
                        ], style=panel_content_style)
                    ], style=panel_style)
                ], width=3),

                # En Sağ Panel - Properties
                dbc.Col([
                    html.Div([
                        # Tab başlıkları
                        html.Div([
                            html.Div("Properties", style=active_tab_style)
                        ], style={"display": "flex", "marginBottom": "0"}),

                        # Panel içeriği
                        html.Div(id='properties-panel-content', children=[
                            html.Div([
                                html.I(className="fas fa-cog",
                                       style={"marginRight": "8px", "color": "#6f42c1"}),
                                "Veri yüklendikten sonra özellikler burada görünecek"
                            ], style={"padding": "12px", "color": "#6c757d", "textAlign": "center"})
                        ], style=panel_content_style)
                    ], style=panel_style)
                ], width=3)
            ], style={"margin": "16px 0"})
        ], fluid=True)
    ], style={"backgroundColor": "#f5f5f5", "minHeight": "100vh", "padding": "0"}),

    # Store ve Interval bileşenleri
    dcc.Store(id='upload-progress-store', data={'progress': 0, 'uploading': False}),
    dcc.Store(id='selected-analysis-store', data=None),
    dcc.Store(id='file-data-store', data={}),
    dcc.Store(id='freq-res-store', data={'type': 'lines', 'value': 512}),
    dcc.Store(id='selected-headers-store', data={}),
    dcc.Store(id='filtered-dataframe-store', data=None),  # Sadece filtreli veri

    # Uzun hesaplamalar için loading bileşeni
    dcc.Loading(
        id="loading-analysis",
        type="circle",
        children=[html.Div(id="loading-output", style={'display': 'none'})],
        style={'position': 'fixed', 'top': '50%', 'left': '50%', 'transform': 'translate(-50%, -50%)',
               'display': 'none'}
    ),

    # Analiz ilerlemesini kontrol için interval
    dcc.Interval(id='analysis-check-interval', interval=500, n_intervals=0, disabled=True),

    dcc.Interval(id='progress-interval', interval=500, n_intervals=0, disabled=True)
    # Interval süresi 500ms'ye çıkarıldı
])


# Header seçim bölümünü oluşturma callback'i
@app.callback(
    Output('header-selection-container', 'children'),
    [Input('file-data-store', 'data')],
    prevent_initial_call=True
)
def create_header_selection(file_data):
    if not file_data:
        return []

    all_headers = {}

    for filename, file_info in file_data.items():
        data = file_info['data']
        headers = list(data.keys())

        for header in headers:
            if 'time' in header.lower():
                continue  # ⛔ Zaman sütunlarını gösterme

            if header not in all_headers:
                unit = ""
                if '(' in header and ')' in header:
                    unit_start = header.rfind('(')
                    unit_end = header.rfind(')')
                    if unit_start < unit_end:
                        unit = header[unit_start + 1:unit_end]

                header_lower = header.lower()
                if 'rpm' in header_lower:
                    channel_group = 'Tacho'
                elif any(axis in header_lower for axis in ['x', 'y', 'z']):
                    channel_group = 'Vibration'
                else:
                    channel_group = 'Acoustic'

                all_headers[header] = {
                    'unit': unit,
                    'channel_group': channel_group
                }

    if not all_headers:
        return []

    # En fazla 10 başlık göster
    limited_headers = dict(list(all_headers.items())[:10])

    header_selection_card = html.Div([
        html.H6("Header Seçimi",
                style={'color': '#495057', 'marginBottom': '15px', 'fontSize': '14px', 'fontWeight': 'bold'}),
        html.Div([
            html.Div([
                dbc.Checklist(
                    id='header-selection-checkboxes',
                    options=[
                        {
                            "label": html.Div([
                                html.Span(header, style={'fontWeight': '500', 'fontSize': '12px'}),
                                html.Br(),
                                html.Span(f"Unit: {info['unit'] or '-'}",
                                          style={'fontSize': '10px', 'color': '#6c757d'}),
                                html.Br(),
                                html.Span(f"ChannelGroup: {info['channel_group']}",
                                          style={'fontSize': '10px', 'color': '#6c757d'})
                            ]),
                            "value": header
                        } for header, info in limited_headers.items()
                    ],
                    value=list(limited_headers.keys())[:3] if len(limited_headers) > 3 else list(
                        limited_headers.keys()),
                    style={'margin': '0'}
                )
            ], style={
                'maxHeight': '300px',
                'overflowY': 'auto',
                'padding': '10px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '6px',
                'border': '1px solid #e9ecef'
            })
        ])
    ], style={
        'padding': '15px',
        'backgroundColor': '#ffffff',
        'border': '1px solid #dee2e6',
        'borderRadius': '8px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.1)'
    })

    return header_selection_card


# Seçilen headerları saklama callback'i
@app.callback(
    Output('selected-headers-store', 'data'),
    [Input('header-selection-checkboxes', 'value')],
    prevent_initial_call=True
)
def store_selected_headers(selected_headers):
    return {'headers': selected_headers[:10] if selected_headers else []}  # Max 10 başlık


# Seçilen analiz türünü saklama callback'i
@app.callback(
    Output('selected-analysis-store', 'data'),
    [Input('analysis-type-radio', 'value')],
    prevent_initial_call=True
)
def store_selected_analysis(selected_value):
    return selected_value


# Properties panelini güncelleme callback'i
@app.callback(
    Output('properties-panel-content', 'children'),
    [Input('selected-analysis-store', 'data'),
     Input('file-data-store', 'data'),
     Input('freq-res-store', 'data')],
    prevent_initial_call=True
)
def update_properties_panel(selected_analysis, file_data, freq_res_data):
    if selected_analysis == "FFTvsTime":
        # FFT vs Time için özel kontrol paneli
        return html.Div([
            dbc.Card([
                dbc.CardBody([
                    html.H5("FFT vs Time Ayarları", style={"color": "#495057", "marginBottom": "20px"}),

                    # Amplitude Seçimi
                    html.Div([
                        html.Label("Amplitude",
                                   style={"fontWeight": "bold", "marginBottom": "8px", "display": "block"}),
                        dbc.Select(
                            id='amplitude-select',
                            options=[
                                {"label": "Rms", "value": "rms"},
                                {"label": "Peak", "value": "peak"}
                            ],
                            value="rms"
                        )
                    ], style={"marginBottom": "20px"}),

                    # Window Seçimi
                    html.Div([
                        html.Label("Window", style={"fontWeight": "bold", "marginBottom": "8px", "display": "block"}),
                        dbc.Select(
                            id='window-select',
                            options=[{"label": "Hanning", "value": "hanning"}],
                            value="hanning"
                        )
                    ], style={"marginBottom": "20px"}),

                    # Frequency Resolution
                    html.Div([
                        html.Label("Frequency Resolution",
                                   style={"fontWeight": "bold", "marginBottom": "8px", "display": "block"}),
                        html.Div([
                            dbc.Select(
                                id='freq-res-type-select',
                                options=[
                                    {"label": "lines", "value": "lines"},
                                    {"label": "df (Hz)", "value": "df"},
                                    {"label": "block duration (s)", "value": "duration"}
                                ],
                                value=freq_res_data['type'] if freq_res_data else 'lines',
                                style={"width": "48%", "display": "inline-block", "marginRight": "4%"}
                            ),
                            dbc.Select(
                                id='freq-res-value-select',
                                options=[],
                                value=freq_res_data['value'] if freq_res_data else 512,
                                style={"width": "48%", "display": "inline-block"}
                            )
                        ]),
                        html.Div(id='freq-res-note',
                                 style={"fontSize": "12px", "color": "#6c757d", "marginTop": "8px"})
                    ], style={"marginBottom": "20px"}),

                    # Overlap
                    html.Div([
                        html.Label("Overlap", style={"fontWeight": "bold", "marginBottom": "8px", "display": "block"}),
                        dbc.Select(
                            id='overlap-select',
                            options=[
                                {"label": "10%", "value": "10"},
                                {"label": "25%", "value": "25"},
                                {"label": "50%", "value": "50"},
                                {"label": "66.7%", "value": "66.7"},
                                {"label": "75%", "value": "75"},
                                {"label": "90%", "value": "90"}
                            ],
                            value="50"
                        )
                    ], style={"marginBottom": "20px"}),

                    # Frequency Weighting
                    html.Div([
                        html.Label("Frequency Weighting",
                                   style={"fontWeight": "bold", "marginBottom": "8px", "display": "block"}),
                        dbc.Select(
                            id='freq-weighting-select',
                            options=[{"label": "A", "value": "A"}],
                            value="A"
                        )
                    ], style={"marginBottom": "25px"}),

                    # Calculate Overall Level
                    html.Div([
                        dbc.Checklist(
                            id='overall-level-check',
                            options=[{"label": "Calculate overall level", "value": True}],
                            value=[True],
                            switch=True
                        )
                    ]),

                    # Analiz butonu
                    html.Div([
                        dbc.Button(
                            "Analizi Başlat",
                            id="start-analysis-btn",
                            color="primary",
                            className="mt-3"
                        )
                    ], style={"textAlign": "center"})
                ])
            ], style={"borderRadius": "8px", "boxShadow": "0 2px 8px rgba(0,0,0,0.1)"})
        ])

    elif file_data:
        # Dosya özelliklerini göster
        property_cards = []
        for filename, file_info in file_data.items():
            props = file_info['properties']

            card = dbc.Card(
                [
                    dbc.CardHeader(
                        html.Div([
                            html.I(className="fas fa-file-alt", style={"marginRight": "8px"}),
                            props['filename']
                        ], style={"fontWeight": "bold"})
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.Span("Örnek Sayısı:", style={"fontWeight": "bold", "width": "150px"}),
                            html.Span(props['sampling_count'])
                        ], style={"display": "flex", "marginBottom": "8px"}),

                        html.Div([
                            html.Span("Örnekleme Oranı:", style={"fontWeight": "bold", "width": "150px"}),
                            html.Span(props['sampling_rate'])
                        ], style={"display": "flex", "marginBottom": "8px"}),

                        html.Div([
                            html.Span("Başlangıç Zamanı:", style={"fontWeight": "bold", "width": "150px"}),
                            html.Span(props['start_time'])
                        ], style={"display": "flex", "marginBottom": "8px"}),

                        html.Div([
                            html.Span("Bitiş Zamanı:", style={"fontWeight": "bold", "width": "150px"}),
                            html.Span(props['end_time'])
                        ], style={"display": "flex", "marginBottom": "8px"}),

                        html.Div([
                            html.Span("Toplam Süre:", style={"fontWeight": "bold", "width": "150px"}),
                            html.Span(props['duration'])
                        ], style={"display": "flex"})
                    ])
                ],
                style={"marginBottom": "15px", "borderRadius": "8px", "boxShadow": "0 2px 5px rgba(0,0,0,0.1)"}
            )
            property_cards.append(card)

        return property_cards

    return html.Div([
        html.I(className="fas fa-cog", style={"marginRight": "8px", "color": "#6f42c1"}),
        "Veri yüklendikten sonra özellikler burada görünecek"
    ], style={"padding": "12px", "color": "#6c757d", "textAlign": "center"})


# Frekans çözünürlüğü değer seçeneklerini güncelleme - KARARLI VERSİYON
@app.callback(
    Output('freq-res-value-select', 'options'),
    Output('freq-res-value-select', 'value'),
    Input('freq-res-type-select', 'value'),
    State('freq-res-store', 'data'),
    prevent_initial_call=True
)
def update_freq_res_options(res_type, freq_res_data):
    if not res_type:
        return [], None

    # Mevcut değeri kontrol et
    current_value = None
    if freq_res_data and freq_res_data['type'] == res_type:
        current_value = freq_res_data['value']

    if res_type == "lines":
        options = [{"label": f"{line} lines", "value": line} for line in [512, 1024, 2048, 4096]]
        # Mevcut değer seçenekler arasında değilse varsayılan ata
        value = current_value if current_value in [512, 1024, 2048, 4096] else 512
        return options, value

    elif res_type == "df":
        options = [{"label": f"{df} Hz", "value": df} for df in [0.1, 0.5, 1, 2]]
        value = current_value if current_value in [0.1, 0.5, 1, 2] else 1
        return options, value

    elif res_type == "duration":
        options = [{"label": f"{dur} s", "value": dur} for dur in [0.1, 0.5, 1, 2]]
        value = current_value if current_value in [0.1, 0.5, 1, 2] else 1
        return options, value

    return [], None


# Frekans çözünürlüğü değerini saklama - KARARLI VERSİYON
@app.callback(
    Output('freq-res-store', 'data'),
    Input('freq-res-type-select', 'value'),
    Input('freq-res-value-select', 'value'),
    State('freq-res-store', 'data'),
    prevent_initial_call=True
)
def store_freq_res_values(res_type, res_value, current_data):
    if not res_type or not res_value:
        return dash.no_update

    # Eğer mevcut veri yoksa yeni oluştur
    if not current_data:
        return {'type': res_type, 'value': res_value}

    # Eğer tür değiştiyse yeni veri oluştur
    if current_data['type'] != res_type:
        return {'type': res_type, 'value': res_value}

    # Sadece değer güncellenmişse mevcut veriyi güncelle
    if current_data['value'] != res_value:
        current_data['value'] = res_value
        return current_data

    return dash.no_update


# Not kısmını güncelleme - KARARLI VERSİYON
@app.callback(
    Output('freq-res-note', 'children'),
    Input('freq-res-store', 'data'),
    State('file-data-store', 'data'),
    prevent_initial_call=True
)
def update_note(freq_res_data, file_data):
    if not freq_res_data:
        return html.Span("( lines: , df (Hz): , block duration (s): )", style={"fontStyle": "italic"})

    res_type = freq_res_data.get('type')
    res_value = freq_res_data.get('value')

    if not res_type or not res_value:
        return html.Span("( lines: , df (Hz): , block duration (s): )", style={"fontStyle": "italic"})

    fs = 1000.0  # Varsayılan örnekleme frekansı

    if file_data:
        try:
            # İlk dosyanın özelliklerini al
            first_file = next(iter(file_data.values()))
            props = first_file['properties']
            fs_str = props['sampling_rate'].split()[0]  # "1000.00 Hz" -> "1000.00"
            fs = float(fs_str)
        except:
            fs = 1000.0  # Varsayılan değer

    if res_type == "lines":
        lines = res_value
        df = fs / lines
        duration = lines / fs
        return html.Span(f"( lines: {lines}, df (Hz): {df:.2f}, block duration (s): {duration:.4f} )",
                         style={"fontStyle": "italic"})

    elif res_type == "df":
        df = res_value
        lines = fs / df
        duration = 1 / df
        return html.Span(f"( lines: {lines:.0f}, df (Hz): {df}, block duration (s): {duration:.2f} )",
                         style={"fontStyle": "italic"})

    elif res_type == "duration":
        duration = res_value
        lines = fs * duration
        df = 1 / duration
        return html.Span(f"( lines: {lines:.0f}, df (Hz): {df:.2f}, block duration (s): {duration} )",
                         style={"fontStyle": "italic"})

    return html.Span("( lines: , df (Hz): , block duration (s): )", style={"fontStyle": "italic"})


# Analiz işlemini çalıştıracak fonksiyon (thread içinde çalışacak)
def run_analysis(analysis_type, selected_headers_store, file_data,
                 freq_weighting, freq_res_type, freq_res_value):
    global analysis_result, analysis_running

    try:
        if analysis_type != 'FFTvsTime' or not selected_headers_store or not file_data:
            return

        selected_headers = selected_headers_store.get('headers', [])
        if len(selected_headers) < 2:
            return

        first_file = next(iter(file_data.values()))
        data_dict = first_file['data']

        # Sadece gerekli sütunları seç
        time_col = next((col for col in data_dict if 'time' in col.lower()), None)
        if not time_col:
            return

        # DataFrame'i oluştururken sadece gerekli sütunları al
        required_cols = [time_col] + selected_headers
        df = pd.DataFrame({col: data_dict[col] for col in required_cols if col in data_dict})

        # Büyük verilerde sadece ilk 1000 satır
        if len(df) > 1000:
            df = df.head(1000)

        rpm_col = next((col for col in selected_headers if 'rpm' in col.lower()), None)
        pa_col = next((col for col in selected_headers if any(p in col.lower() for p in ['pa', 'pressure'])), None)

        if not rpm_col or not pa_col:
            return

        time_values = df[time_col].values
        rpm_values = df[rpm_col].values
        pa_values = df[pa_col].values

        block_duration = freq_res_value if freq_res_type == 'duration' else None

        if freq_weighting == 'A':
            fs, weighted_pa = RpmToTimeCsv.calculate_sample_rate(time_values, pa_values)
            result_df = TimeToRpmCsv.analyze_time_series(time_values, rpm_values, time_values, weighted_pa,
                                                         n_blocks=None, block_duration=block_duration,
                                                         t_min=None, t_max=None)
        else:
            result_df = TimeToRpmCsv.analyze_time_series(time_values, rpm_values, time_values, pa_values,
                                                         n_blocks=None, block_duration=block_duration,
                                                         t_min=None, t_max=None)

        # Sadece gerekli sütunları döndür
        analysis_result = result_df[['Time', 'RPM', 'Amplitude']].to_dict('records')
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        analysis_result = None
    finally:
        analysis_running = False


# Analiz başlatma callback'i
@app.callback(
    [Output('loading-analysis', 'style'),
     Output('analysis-check-interval', 'disabled')],
    [Input('start-analysis-btn', 'n_clicks')],
    [State('selected-analysis-store', 'data'),
     State('selected-headers-store', 'data'),
     State('file-data-store', 'data'),
     State('freq-weighting-select', 'value'),
     State('freq-res-type-select', 'value'),
     State('freq-res-value-select', 'value')],
    prevent_initial_call=True
)
def start_analysis(n_clicks, analysis_type, selected_headers_store, file_data,
                   freq_weighting, freq_res_type, freq_res_value):
    global analysis_thread, analysis_running

    if n_clicks is None or analysis_running:
        return no_update, no_update

    # Analiz durumunu sıfırla
    analysis_running = True
    analysis_result = None

    # Thread oluştur ve başlat
    analysis_thread = threading.Thread(
        target=run_analysis,
        args=(analysis_type, selected_headers_store, file_data,
              freq_weighting, freq_res_type, freq_res_value)
    )
    analysis_thread.daemon = True
    analysis_thread.start()

    # Loading göster ve interval'i etkinleştir
    return {'display': 'block'}, False


# Analiz sonuç kontrol callback'i
@app.callback(
    [Output('filtered-dataframe-store', 'data'),
     Output('loading-analysis', 'style', allow_duplicate=True),
     Output('analysis-check-interval', 'disabled', allow_duplicate=True)],
    [Input('analysis-check-interval', 'n_intervals')],
    prevent_initial_call=True
)
def check_analysis_progress(n_intervals):
    global analysis_result, analysis_running

    if analysis_running:
        # Hala çalışıyorsa loading göster ve interval devam etsin
        return no_update, {'display': 'block'}, False
    else:
        # Tamamlandıysa sonucu döndür, loading'i gizle ve interval'i durdur
        return analysis_result, {'display': 'none'}, True


# Dosya yükleme ve veri işleme callback'i
@app.callback(
    [Output('upload-progress-store', 'data'),
     Output('progress-interval', 'disabled'),
     Output('file-data-store', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('file-data-store', 'data')],
    prevent_initial_call=True
)
def handle_file_upload(contents, filenames, existing_data):
    if not contents:
        return {'progress': 0, 'uploading': False, 'filenames': [], 'total_files': 0}, True, existing_data

    if not isinstance(contents, list):
        contents = [contents]
        filenames = [filenames]

    # Mevcut veriyi kopyala
    new_data = existing_data.copy()

    for content, filename in zip(contents, filenames):
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)

        try:
            if 'rsp' in filename.lower():
                # RSP dosyasını işle
                with tempfile.NamedTemporaryFile(delete=False, suffix='.rsp') as temp_file:
                    temp_file.write(decoded)
                    temp_file_path = temp_file.name

                rpc = ReadRPC(temp_file_path)
                rpc.parse()
                df = rpc.to_dataframe()

                # İlgili sütunları seç
                df = df[['Time (s)', 'AI C-16/MidSeatMic', 'CNT A-1/EngRpm']]

                # Veri özelliklerini hesapla
                time_values = df['Time (s)'].values
                start_time = np.min(time_values)
                end_time = np.max(time_values)
                duration = end_time - start_time
                sampling_rate = len(df) / duration if duration > 0 else 0

                # Büyük dosyalarda sadece ilk 1000 satır
                if len(df) > 1000:
                    df = df.head(1000)

                # Veriyi sakla
                new_data[filename] = {
                    'data': df.to_dict('list'),
                    'properties': {
                        'filename': filename,
                        'sampling_count': len(df),
                        'sampling_rate': f"{sampling_rate:.2f} Hz" if sampling_rate > 0 else "N/A",
                        'start_time': f"{start_time:.2f} s",
                        'end_time': f"{end_time:.2f} s",
                        'duration': f"{duration:.2f} s"
                    }
                }

            elif 'csv' in filename.lower():
                # CSV dosyasını işle
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))

                # Büyük dosyalarda sadece ilk 1000 satır
                if len(df) > 1000:
                    df = df.head(1000)

                # Veri özelliklerini hesapla (varsayılan sütun adları)
                time_values = df.iloc[:, 0].values  # İlk sütun zaman
                start_time = np.min(time_values)
                end_time = np.max(time_values)
                duration = end_time - start_time
                sampling_rate = len(df) / duration if duration > 0 else 0

                # Veriyi sakla
                new_data[filename] = {
                    'data': df.to_dict('list'),
                    'properties': {
                        'filename': filename,
                        'sampling_count': len(df),
                        'sampling_rate': f"{sampling_rate:.2f} Hz" if sampling_rate > 0 else "N/A",
                        'start_time': f"{start_time:.2f} s",
                        'end_time': f"{end_time:.2f} s",
                        'duration': f"{duration:.2f} s"
                    }
                }

            elif 'xlsx' in filename.lower():
                # Excel dosyasını işle
                df = pd.read_excel(io.BytesIO(decoded))

                # Büyük dosyalarda sadece ilk 1000 satır
                if len(df) > 1000:
                    df = df.head(1000)

                # Veri özelliklerini hesapla (varsayılan sütun adları)
                time_values = df.iloc[:, 0].values  # İlk sütun zaman
                start_time = np.min(time_values)
                end_time = np.max(time_values)
                duration = end_time - start_time
                sampling_rate = len(df) / duration if duration > 0 else 0

                # Veriyi sakla
                new_data[filename] = {
                    'data': df.to_dict('list'),
                    'properties': {
                        'filename': filename,
                        'sampling_count': len(df),
                        'sampling_rate': f"{sampling_rate:.2f} Hz" if sampling_rate > 0 else "N/A",
                        'start_time': f"{start_time:.2f} s",
                        'end_time': f"{end_time:.2f} s",
                        'duration': f"{duration:.2f} s"
                    }
                }

        except Exception as e:
            print(f"Error processing file {filename}: {str(e)}")

    return {'progress': 0, 'uploading': True, 'filenames': filenames, 'total_files': len(filenames)}, False, new_data


# Progress bar güncelleme callback'i
@app.callback(
    [Output('upload-progress', 'value'),
     Output('upload-progress', 'style'),
     Output('upload-progress-store', 'data', allow_duplicate=True),
     Output('progress-interval', 'disabled', allow_duplicate=True)],
    [Input('progress-interval', 'n_intervals')],
    [State('upload-progress-store', 'data')],
    prevent_initial_call=True
)
def update_progress(n_intervals, store_data):
    if not store_data.get('uploading', False):
        return 0, {'display': 'none'}, store_data, True

    current_progress = store_data.get('progress', 0)
    total_files = store_data.get('total_files', 1)

    if current_progress < 100:
        increment = max(3, 100 // (total_files * 8))
        new_progress = min(current_progress + increment, 100)

        if new_progress == 100:
            return new_progress, {'display': 'block', 'height': '6px'}, {
                'progress': new_progress,
                'uploading': False,
                'filenames': store_data.get('filenames', []),
                'total_files': total_files,
                'completed': True
            }, True
        else:
            return new_progress, {'display': 'block', 'height': '6px'}, {
                'progress': new_progress,
                'uploading': True,
                'filenames': store_data.get('filenames', []),
                'total_files': total_files
            }, False

    return current_progress, {'display': 'block', 'height': '6px'}, store_data, True


# Yüklenen dosya kartları callback'i
@app.callback(
    Output('uploaded-files-container', 'children'),
    [Input('upload-progress-store', 'data')],
    prevent_initial_call=True
)
def display_uploaded_files(store_data):
    if not store_data or not store_data.get('completed', False) or not store_data.get('filenames'):
        return []

    filenames = store_data['filenames']

    file_cards = []
    for i, filename in enumerate(filenames):
        # Dosya tipine göre ikon ve renk
        if filename.endswith('.csv'):
            icon = "fas fa-file-csv"
            color = "#28a745"
        elif filename.endswith('.xlsx'):
            icon = "fas fa-file-excel"
            color = "#17a2b8"
        elif filename.endswith('.rsp'):
            icon = "fas fa-file-code"
            color = "#6f42c1"
        else:
            icon = "fas fa-file"
            color = "#6c757d"

        # Modern dosya kartı
        file_card = html.Div([
            html.Div([
                html.I(className=icon,
                       style={"fontSize": "20px", "color": color, "marginRight": "12px"}),
                html.Div(
                    filename,
                    style={"fontSize": "13px", "fontWeight": "600", "color": "#495057"}
                )
            ], style={"display": "flex", "alignItems": "center", "flex": "1"}),

            html.Div([
                dbc.Checklist(
                    id=f"file-checkbox-{i}",
                    options=[{"label": "", "value": filename}],
                    value=[filename],
                    inline=True,
                    style={"margin": "0"}
                )
            ])
        ], style={
            'backgroundColor': '#ffffff',
            'border': '1px solid #e9ecef',
            'borderRadius': '6px',
            'padding': '10px',
            'margin': '6px 0',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'space-between'
        })

        file_cards.append(file_card)

    return file_cards


if __name__ == "__main__":
    app.run(debug=True, threaded=True)  # Threaded mode for better concurrency