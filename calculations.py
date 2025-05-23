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


class TimeToRpmRsp:
    def __init__(self, file_pattern="*ornek_data_04.csv", rpm_step=25):
        self.file_pattern = file_pattern
        self.rpm_step = rpm_step

    def read_rsp_file(self, file_path):
        """
        RPC dosyasını okuyup veri, başlık ve kanal bilgilerini döndürür.
        """
        rpc_file_path = pathlib.Path(file_path)
        rpc_object = ReadRPC(rpc_file_path)
        rpc_object.import_rpc_data_from_file()

        headers = rpc_object.get_headers()
        channels = rpc_object.get_channels()
        data = rpc_object.get_data()

        return headers, channels, data

    def create_dataframe(self, data, channels, delta_t):
        """
        NumPy verisi ve kanal isimlerinden DataFrame oluşturur.
        """
        num_samples = data.shape[0]
        sampling_rate = 1 / delta_t
        time = np.linspace(0, (num_samples - 1) / sampling_rate, num_samples)

        df_dict = {"time": time}
        for i, channel in enumerate(channels):
            df_dict[channel] = data[:, i]

        df = pd.DataFrame(df_dict)
        df.columns = ["time", "pa", "rpm"]
        return df

    def calculate_n_blocks(self, rpm_data):
        """RPM verisine göre blok sayısını hesaplar."""
        max_rpm = int(max(rpm_data))
        min_rpm = int(min(rpm_data))
        return int((max_rpm - min_rpm) / self.rpm_step) + 1

    def calculate_a_weighted_pressure(self, time_data, pressure_data):
        """A-ağırlıklı basınç hesaplamasını yapar."""
        delta_t = time_data[1] - time_data[0]  # İki örnek arasındaki zaman farkı
        fs = 1 / delta_t  # Örnekleme frekansı (Hz)

        # A-ağırlıklı basınç verisini hesaplama
        a_weighted_data = waveform_analysis.A_weight(pressure_data, fs)

        return a_weighted_data

    def analyze_time_series(self, t_data, rpm_data, s_data, pa_data, n_block):
        """Zaman serisi verilerini analiz eder."""
        # PA verilerine göre 56 eşit zaman bloğu oluşturma
        t_start = t_data.min()
        t_end = t_data.max()
        time_blocks = np.linspace(t_start, t_end, n_block + 1)

        # Sonuçları saklamak için listeler
        mean_rpms = []
        rms_pas = []
        block_starts = []
        block_ends = []

        # Her blok için analiz
        for i in range(len(time_blocks) - 1):
            t0 = time_blocks[i]
            t1 = time_blocks[i + 1]

            # RPM değerlerini filtreleme ve ortalama alma
            rpm_mask = (s_data >= t0) & (s_data <= t1)
            block_rpm = rpm_data[rpm_mask]
            mean_rpm = np.mean(block_rpm) if len(block_rpm) > 0 else np.nan

            # PA değerlerini filtreleme ve RMS hesaplama
            pa_mask = (t_data >= t0) & (t_data <= t1)
            pa_values = pa_data[pa_mask]

            # PA RMS hesaplama
            if len(pa_values) > 0:
                block = pa_values
                overall_pa = np.sqrt(np.mean(block**2))
                overall = 20 * np.log10(overall_pa / (2 * 10**-5))  # dB(A) dönüşümü
            else:
                overall = np.nan

            # Sonuçları listelere ekleme
            mean_rpms.append(mean_rpm)
            rms_pas.append(overall)
            block_starts.append(t0)
            block_ends.append(t1)

        return mean_rpms, rms_pas

    def plot_results(self, mean_rpms, rms_pas):
        """Analiz sonuçlarını görselleştirir."""
        fig, (ax2) = plt.subplots(1, 1, figsize=(12, 8))
        # PA RMS plot
        ax2.plot(mean_rpms, rms_pas, color='black', label='Yazılım')
        ax2.set_xlabel('RPM')
        ax2.set_ylabel('dB(A)')
        ax2.set_title('PA RMS vs RPM')
        ax2.grid(True)
        ax2.legend()
        plt.tight_layout()
        plt.show()
        st.pyplot(fig)

class RpmToTimeRsp:
    def read_rsp_file(self, file_path):
        """
        RPC dosyasını okuyup veri, başlık ve kanal bilgilerini döndürür.
        """
        rpc_file_path = pathlib.Path(file_path)
        rpc_object = ReadRPC(rpc_file_path)
        rpc_object.import_rpc_data_from_file()

        headers = rpc_object.get_headers()
        channels = rpc_object.get_channels()
        data = rpc_object.get_data()

        return headers, channels, data

    def create_dataframe(self, data, channels, delta_t):
        """
        NumPy verisi ve kanal isimlerinden DataFrame oluşturur.
        """
        num_samples = data.shape[0]
        sampling_rate = 1 / delta_t
        time = np.linspace(0, (num_samples - 1) / sampling_rate, num_samples)

        df_dict = {"time": time}
        for i, channel in enumerate(channels):
            df_dict[channel] = data[:, i]

        df = pd.DataFrame(df_dict)
        df.columns = ["time", "pa", "rpm"]
        return df

    def calculate_sample_rate(self, t_data, pa_data):
        """
        Örneklem frekansını hesaplar ve A-ağırlık filtresi uygular
        """
        deltaT = t_data[1] - t_data[0]
        fs = 1 / deltaT
        weighted_pa = waveform_analysis.A_weight(pa_data, fs)
        return fs, weighted_pa

    def process_rpm_data(self, rpm_data, t_data, pa_data, 
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
                time_section[time_section >= last_end_time]

                if len(time_section) > 0:
                    start_time = np.min(time_section)
                    end_time = np.max(time_section)
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

        return rpm_list, dB_values

class TimeToRpmCsv:
    def analyze_time_series(time_rpm, rpm, time_pa, pa, n_blocks):
        # Veri tiplerini numpy array'e çevirme
        time_rpm = np.array(time_rpm)
        rpm = np.array(rpm)
        time_pa = np.array(time_pa)
        pa = np.array(pa)

        # PA verilerine göre 56 eşit zaman bloğu oluşturma
        t_start = time_pa.min()
        t_end = time_pa.max()
        time_blocks = np.linspace(t_start, t_end, n_blocks + 1)

        # Sonuçları saklamak için listeler
        mean_rpms = []
        rms_pas = []
        block_starts = []
        block_ends = []

        # Her blok için analiz
        for i in range(len(time_blocks)-1):
            t0 = time_blocks[i]
            t1 = time_blocks[i+1]

            # RPM değerlerini filtreleme ve ortalama alma
            rpm_mask = (time_rpm >= t0) & (time_rpm <= t1)
            block_rpm = rpm[rpm_mask]
            mean_rpm = np.mean(block_rpm) if len(block_rpm) > 0 else np.nan

            # PA değerlerini filtreleme ve RMS hesaplama
            pa_mask = (time_pa >= t0) & (time_pa <= t1)
            pa_values = pa[pa_mask]

            # PA RMS hesaplama
            if len(pa_values) > 0:
                window = np.hanning(len(pa_values))
                window_correction_factor = np.sqrt(len(pa_values) / np.sum(window**2))
                block = pa_values * window
                overall_pa = np.sqrt(np.mean(block**2)) * np.sqrt(window_correction_factor)
                overall = 20 * np.log10(overall_pa/(2*10**-5))  # dB(A) dönüşü
            else:
                overall = np.nan

            # Sonuçları listelere ekleme
            mean_rpms.append(mean_rpm)
            rms_pas.append(overall)
            block_starts.append(t0)
            block_ends.append(t1)
        df = pd.DataFrame({
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
    def calculate_sample_rate(self, t_data, pa_data):
        """
        Örneklem frekansını hesaplar ve A-ağırlık filtresi uygular
        """
        deltaT = t_data[1] - t_data[0]
        fs = 1 / deltaT
        weighted_pa = waveform_analysis.A_weight(pa_data, fs)
        return fs, weighted_pa

    def process_rpm_data(self, rpm_data, t_data, pa_data, 
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

        return rpm_list, dB_values
    
