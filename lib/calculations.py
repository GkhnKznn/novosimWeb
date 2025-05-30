import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import waveform_analysis
import glob
import streamlit as st
import pathlib
from rpc_reader.rpc_reader import ReadRPC
import sys
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
import plotly.express as px

class TimeToRpmCsv:
    def analyze_time_series(time_rpm, rpm, time_pa, pa, n_blocks=None, block_duration=None, t_min=None, t_max=None):
        time_rpm = np.array(time_rpm)
        rpm = np.array(rpm)
        time_pa = np.array(time_pa)
        pa = np.array(pa)

        t_start = t_min if t_min is not None else time_pa.min()
        t_end = t_max if t_max is not None else time_pa.max()

        if block_duration is not None:
            time_blocks = np.arange(t_start, t_end + block_duration, block_duration)
        elif n_blocks is not None:
            time_blocks = np.linspace(t_start, t_end, n_blocks + 1)
        else:
            raise ValueError("Either block_duration or n_blocks must be provided.")

        mean_rpms = []
        rms_pas = []
        block_starts = []
        block_ends = []

        for i in range(len(time_blocks) - 1):
            t0 = time_blocks[i]
            t1 = time_blocks[i + 1]

            rpm_mask = (time_rpm >= t0) & (time_rpm <= t1)
            block_rpm = rpm[rpm_mask]
            mean_rpm = np.mean(block_rpm) if len(block_rpm) > 0 else np.nan

            pa_mask = (time_pa >= t0) & (time_pa <= t1)
            pa_values = pa[pa_mask]

            if len(pa_values) > 0:
                window = np.hanning(len(pa_values))
                window_correction_factor = np.sqrt(len(pa_values) / np.sum(window ** 2))
                block = pa_values * window
                overall_pa = np.sqrt(np.mean(block ** 2)) * np.sqrt(window_correction_factor)
                overall = 20 * np.log10(overall_pa / (2 * 10 ** -5))
            else:
                overall = np.nan

            mean_rpms.append(mean_rpm)
            rms_pas.append(overall)
            block_starts.append(t0)
            block_ends.append(t1)

        df = pd.DataFrame({
            'start_time': block_starts,
            'end_time': block_ends,
            'rpm': mean_rpms,
            'rms': rms_pas
        })
        return df

    def plotRpmToTime(df: pd.DataFrame):
        """
        İki sütunlu bir DataFrame alarak scatter plot oluşturur.

        Args:
            df: İki sütunlu pandas DataFrame

        Returns:
            Plotly Figure nesnesi
        """
        # DataFrame'in iki sütunu olduğunu kontrol et
        if df.shape[1] != 2:
            raise ValueError(f"DataFrame tam olarak iki sütun içermelidir. Şu anda {df.shape[1]} sütun var.")

        # Sütun adlarını al
        x_column = df.columns[0]
        y_column = df.columns[1]

        # Scatter plot oluştur
        fig = px.scatter(df, x=x_column, y=y_column,
                         title=f"{x_column} ve {y_column} Karşılaştırması",
                         template="plotly_white")

        # Grafik ayarları
        fig.update_layout(
            plot_bgcolor='rgba(240,240,240,1)',
            paper_bgcolor='rgba(255,255,255,0.8)'
        )

        return fig


class RpmToTimeCsv:
    def calculate_sample_rate( t_data, pa_data):
        """
        Örneklem frekansını hesaplar ve A-ağırlık filtresi uygular
        """
        deltaT = t_data[1] - t_data[0]
        fs = 1 / deltaT
        weighted_pa = waveform_analysis.A_weight(pa_data, fs)
        return fs, weighted_pa

    def process_rpm_data( rpm_data, t_data, pa_data,
                         start_rpm_step=25, window_type='hann'):
        """
        RPM aralıklarını işleyip dB(A) değerlerini hesaplar

        Parametreler:
        - rpm_data: RPM değerleri array'i
        - s_data: Zaman damgaları array'i
        - t_data: Hizalı zaman array'i
        - pa_data: Ağırlıklandırılmış basınç verisi
        - start_rpm_step: RPM artış adımı (default 25)
        - window_type: Pencereleme fonksiyonu (default hann)

        Çıktı:
        - (rpm_list, dB_values): RPM ve karşılık gelen dB(A) listeleri
        """
        window_functions = {
            'hann': np.hanning,
            'hamming': np.hamming,
            'blackman': np.blackman
        }
        window = window_functions.get(window_type, np.hanning)

        current_rpm = int(np.min(rpm_data))
        last_end_time = np.min(t_data)
        rpm_list = []
        dB_values = []

        while current_rpm < np.max(rpm_data):
            next_rpm = current_rpm + start_rpm_step
            mask = (rpm_data >= current_rpm) & (rpm_data < next_rpm)
            rpm_section = rpm_data[mask]
            time_section = t_data[mask]

            if len(rpm_section) > 0:
                valid_times = time_section[time_section >= last_end_time]

                if len(valid_times) > 0:
                    start_time = np.min(valid_times)
                    end_time = np.max(valid_times)
                    pa_mask = (t_data >= start_time) & (t_data < end_time)
                    pa_values = pa_data[pa_mask]

                    if len(pa_values) > 0:
                        N = len(pa_values)
                        win = window(N)
                        correction = np.sqrt(N / np.sum(win**2))
                        rms = np.sqrt(np.mean((pa_values * win)**2)) * correction
                        dB = 20 * np.log10(rms/(2e-5))
                        rpm_list.append(np.mean(rpm_section))
                        dB_values.append(dB)
                        last_end_time = end_time

            current_rpm = next_rpm
        df = pd.DataFrame({
            'rpm': rpm_list,
            'overall': dB_values
        })
        return df
    
