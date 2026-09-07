# (Salin seluruh kode ini)
import tkinter as tk
from tkinter import scrolledtext, messagebox, font, filedialog
import serial
import threading
import time
from collections import deque
import numpy as np
import joblib
import pywt
import pandas as pd
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

# (Fungsi extract_features dan get_resource_path tidak diubah)
def extract_features(data_series):
    features = {}
    features['mean'] = data_series.mean(); features['std_dev'] = data_series.std(); features['variance'] = data_series.var(); features['max_val'] = data_series.max(); features['min_val'] = data_series.min(); features['skewness'] = data_series.skew(); features['kurtosis'] = data_series.kurtosis()
    zero_crossings = np.where(np.diff(np.sign(data_series)))[0]
    features['zcr'] = len(zero_crossings) / len(data_series) if len(data_series) > 0 else 0
    coeffs = pywt.wavedec(data_series, 'db4', level=4)
    cA4, cD4, cD3, cD2, cD1 = coeffs
    features['energy_d1'] = np.sum(np.square(cD1)); features['energy_d2'] = np.sum(np.square(cD2)); features['energy_d3'] = np.sum(np.square(cD3)); features['energy_d4'] = np.sum(np.square(cD4)); features['energy_a4'] = np.sum(np.square(cA4))
    return features

def get_resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return str(base_path / relative_path)


def available_serial_ports():
    """Return common serial device names for the current operating system."""
    if sys.platform.startswith("win"):
        return [f"COM{i}" for i in range(1, 21)]
    return [f"/dev/{name}" for name in ("ttyACM0", "ttyACM1", "ttyUSB0", "ttyUSB1")]


class SawitDetectorApp:
    def __init__(self, root):
        self.root = root; self.mode = None
        if not self.ask_for_mode(): self.root.destroy(); return
        self.root.title(f"Palm Disease Detection - {self.mode.upper()}"); self.root.geometry("900x800")
        self.collection_duration = 120; self.interim_prediction_interval = 30; self.max_plot_points = 150
        self.model = None; self.scaler = None; self.ser = None; self.is_running = False; self.start_time = 0
        self.plot_data = deque(maxlen=self.max_plot_points); self.all_collected_data = []; self.log_data_realtime = []
        self.raw_data_buffer = deque(maxlen=5)
        self.setup_gui()
        self.load_model_and_scaler()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # (setup_gui, log, find_com_port, and click_start_button are unchanged)
    def setup_gui(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        title_font=font.Font(family="Helvetica", size=18, weight="bold");status_font=font.Font(family="Helvetica", size=14, weight="bold");freq_font=font.Font(family="Helvetica", size=28, weight="bold");result_font=font.Font(family="Helvetica", size=16, weight="bold")
        tk.Label(self.root, text="Palm Disease Detection Monitor", font=title_font, pady=10).pack()
        control_frame = tk.Frame(self.root); control_frame.pack(pady=5)
        tk.Label(control_frame, text="Detection Duration (Minutes):", font=status_font).pack(side=tk.LEFT, padx=(0, 5))
        self.duration_var = tk.StringVar(value="2"); self.duration_entry = tk.Entry(control_frame, textvariable=self.duration_var, font=status_font, width=5); self.duration_entry.pack(side=tk.LEFT)
        plot_frame = tk.Frame(self.root); plot_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self.fig = Figure(figsize=(5, 3), dpi=100); self.ax = self.fig.add_subplot(111); self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame); self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        info_frame = tk.Frame(self.root, pady=10); info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(0, weight=1); info_frame.columnconfigure(1, weight=1)
        left_frame = tk.Frame(info_frame); left_frame.grid(row=0, column=0, sticky="ew")
        self.freq_label = tk.Label(left_frame, text="0 Hz", font=freq_font, fg="navy"); self.freq_label.pack()
        self.timer_label = tk.Label(left_frame, text="Time: 00:00 / 02:00 Minutes", font=status_font); self.timer_label.pack()
        right_frame = tk.Frame(info_frame); right_frame.grid(row=0, column=1, sticky="ew")
        self.interim_result_label = tk.Label(right_frame, text="Interim Result: -", font=result_font, fg="gray"); self.interim_result_label.pack()
        self.final_result_label = tk.Label(right_frame, text="Final Result: Ready", font=status_font, fg="black"); self.final_result_label.pack()
        button_frame = tk.Frame(self.root); button_frame.pack(pady=10)
        self.start_button = tk.Button(button_frame, text="START", command=self.click_start_button, font=status_font, bg="#4CAF50", fg="white", relief=tk.RAISED); self.start_button.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)
        self.stop_button = tk.Button(button_frame, text="STOP & Analyze", command=self.stop_and_analyze, font=status_font, bg="#f44336", fg="white", state=tk.DISABLED, relief=tk.RAISED); self.stop_button.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)
        log_frame = tk.LabelFrame(self.root, text="Status Log", font=status_font, padx=5, pady=5)
        log_frame.pack(fill=tk.X, expand=False, padx=10, pady=(5, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, state=tk.DISABLED, font=("Courier New", 9))
        self.log_text.pack(fill=tk.X, expand=True)
    def log(self, message):
        print(message)
        def append_log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append_log)
    def find_com_port(self):
        self.log("Searching for a sensor on available serial ports...")
        available_ports = available_serial_ports()
        for port in available_ports:
            try:
                self.log(f"Trying port {port}...")
                temp_ser = serial.Serial(port, 9600, timeout=2)
                time.sleep(2)
                if temp_ser.in_waiting > 0:
                    line = temp_ser.readline().decode('utf-8').strip()
                    if not line:
                        self.log(f"-> {port} is open, but is not sending data.")
                        temp_ser.close(); continue
                    int(line)
                    self.ser = temp_ser
                    self.ser.reset_input_buffer()
                    self.log(f"Active sensor found on {port}!")
                    self.root.after(0, lambda p=port: self.final_result_label.config(text=f"Connected to {p}", fg="green"))
                    return True
                else:
                    self.log(f"-> {port} is open, but no data was received.")
                    temp_ser.close()
            except serial.SerialException:
                self.log(f"-> Failed to open {port}.")
                continue
            except (ValueError, UnicodeDecodeError):
                self.log(f"-> {port} sent data in an invalid format (not a number).")
                temp_ser.close()
                continue
        self.log("Sensor not found!")
        messagebox.showerror("Error", "Sensor not found! Make sure it is connected and sending valid numeric data.")
        self.root.after(0, lambda: self.final_result_label.config(text="Sensor Not Found", fg="red"))
        return False
    def click_start_button(self):
        self.log_text.config(state=tk.NORMAL); self.log_text.delete('1.0', tk.END); self.log_text.config(state=tk.DISABLED)
        try:
            duration_minutes = float(self.duration_var.get())
            if duration_minutes <= 0: raise ValueError
            self.collection_duration = int(duration_minutes * 60)
        except ValueError:
                messagebox.showerror("Invalid Input", "Enter a positive duration."); return
        self.start_button.config(state=tk.DISABLED); self.duration_entry.config(state=tk.DISABLED); self.stop_button.config(state=tk.NORMAL)
        self.plot_data.clear(); self.all_collected_data = []; self.log_data_realtime = []
        self.raw_data_buffer.clear()
        self._start_monitoring_thread()
    
    # <<< MODIFIKASI >>>
    # Logika penyimpanan dipindah dari on_closing ke make_final_prediction
    def on_closing(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    def make_final_prediction(self):
        self.final_result_label.config(text="Analyzing all data...", fg="blue")
        self.root.update()
        prediction = self._predict_from_data(self.all_collected_data)

        if prediction:
            color = "red" if prediction != "Tahap-0" else "green"
            self.final_result_label.config(text=f"Final Result: {prediction}", fg=color)
            messagebox.showinfo("Analysis Complete", f"Based on the data analysis, the detection result is:\n\n{prediction}")
        else:
            self.final_result_label.config(text="Analysis Failed (Insufficient Data)", fg="red")
            messagebox.showwarning("Warning", "Too little data was recorded for an accurate analysis.")
        
        # <<< MODIFIKASI DIMULAI DI SINI >>>
        # Tanyakan ke pengguna apakah mau menyimpan data
        if self.mode == 'realtime' and self.log_data_realtime:
            answer = messagebox.askyesno("Save Data", "Would you like to save this recording to a CSV file?")
            if answer:
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                # Buka dialog "Save As"
                filepath = filedialog.asksaveasfilename(
                    initialfile=f"rekaman_sawit_{timestamp}.csv",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                
                # Jika pengguna memilih file (tidak membatalkan)
                if filepath:
                    try:
                        df_log = pd.DataFrame(self.log_data_realtime, columns=['frekuensi_mentah'])
                        df_log.to_csv(filepath, index=False)
                        self.log(f"Data saved to: {filepath}")
                        messagebox.showinfo("Success", f"Recording data was saved as\n{os.path.basename(filepath)}")
                    except Exception as e:
                        self.log(f"Failed to save file: {e}")
                        messagebox.showerror("Failed", f"An error occurred while saving the file:\n{e}")
        # <<< END OF MODIFICATION >>>

        self.reset_buttons()

    # (The remaining functions are unchanged apart from minor updates)
    def monitoring_loop_realtime(self):
        if not self.find_com_port(): self.is_running = False; self.root.after(0, self.reset_buttons); return
        self.start_time = time.time()
        while self.is_running:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    raw_freq = int(line)
                    self.raw_data_buffer.append(raw_freq)
                    smoothed_freq = int(np.mean(self.raw_data_buffer))
                    self.plot_data.append(smoothed_freq)
                    self.all_collected_data.append(smoothed_freq)
                    self.log_data_realtime.append(raw_freq)
                    self.check_for_interim_prediction()
            except (ValueError, serial.SerialException, UnicodeDecodeError) as e:
                self.log(f"Error reading data: {e}"); time.sleep(0.5)
        self.root.after(0, self.make_final_prediction)
    def ask_for_mode(self):
        answer = messagebox.askyesno("Select Mode", "Run REAL-TIME mode with a sensor?\n\nSelect 'No' for SIMULATION mode using a CSV file.")
        if answer: self.mode = 'realtime'; return True
        else:
            self.mode = 'simulation'
            csv_path = filedialog.askopenfilename(title="Select CSV File for Simulation", filetypes=[("CSV Files", "*.csv")])
            if not csv_path: return False
            try: self.csv_data = pd.read_csv(csv_path)['frekuensi'].dropna().tolist(); return True
            except Exception as e: messagebox.showerror("CSV Read Error", f"Failed to read the CSV file.\nError: {e}"); return False
    def load_model_and_scaler(self):
        try:
            model_path = get_resource_path('models/active/model_terbaik_augmented.joblib'); scaler_path = get_resource_path('models/active/scaler_augmented.joblib')
            self.model = joblib.load(model_path); self.scaler = joblib.load(scaler_path)
            self.log("Latest model and scaler loaded successfully."); return True
        except Exception as e:
            self.log(f"Critical Error: Failed to load model/scaler! Error: {e}")
            messagebox.showerror("Critical Error", f"Failed to load model/scaler!\nMake sure the active model files exist in models/active.\n\nError: {e}"); self.root.quit(); return False
    def _start_monitoring_thread(self):
        self.is_running = True; self.final_result_label.config(text="Starting process...", fg="orange")
        target_loop = self.monitoring_loop_realtime if self.mode == 'realtime' else self.monitoring_loop_simulation
        self.monitor_thread = threading.Thread(target=target_loop, daemon=True); self.monitor_thread.start(); self.update_gui()
    def stop_and_analyze(self):
        if self.is_running: self.is_running = False; self.stop_button.config(state=tk.DISABLED, text="Analyzing..."); self.log("Process stopped by the user; continuing with analysis.")
    def monitoring_loop_simulation(self):
        self.start_time = time.time()
        self.log("Starting simulation mode from the CSV file...")
        for freq in self.csv_data:
            if not self.is_running: break
            self.plot_data.append(freq); self.all_collected_data.append(freq); self.check_for_interim_prediction(); time.sleep(0.05)
        self.is_running = False; self.root.after(0, self.make_final_prediction)
        self.log("Simulation complete.")
    def check_for_interim_prediction(self):
        current_time = time.time()
        if not hasattr(self, 'last_interim_time'): self.last_interim_time = self.start_time
        if current_time - self.last_interim_time > self.interim_prediction_interval:
            self.last_interim_time = current_time; threading.Thread(target=self.make_interim_prediction, daemon=True).start()
        if time.time() - self.start_time >= self.collection_duration: self.is_running = False
    def _predict_from_data(self, data):
        if len(data) < 256: return None
        all_features_list = []
        window_size = 256; step = 32
        for i in range(0, len(data) - window_size, step):
            window = data[i : i + window_size]
            if len(window) == window_size: all_features_list.append(extract_features(pd.Series(window)))
        if not all_features_list: return None
        df_features = pd.DataFrame(all_features_list).fillna(0); df_features = df_features[self.scaler.feature_names_in_]
        X_scaled = self.scaler.transform(df_features); predictions = self.model.predict(X_scaled)
        return pd.Series(predictions).mode()[0]
    def make_interim_prediction(self):
        prediction = self._predict_from_data(self.all_collected_data[-512:])
        if prediction: self.root.after(0, lambda: self.interim_result_label.config(text=f"Interim Result: {prediction}", fg="darkorange"))
    def update_gui(self):
        if self.is_running and self.start_time > 0:
            elapsed_seconds = int(time.time() - self.start_time); total_minutes, _ = divmod(self.collection_duration, 60)
            minutes, seconds = divmod(elapsed_seconds, 60)
            self.timer_label.config(text=f"Time: {minutes:02d}:{seconds:02d} / {int(total_minutes):02d}:{int((self.collection_duration % 60)):02d} Minutes")
        current_freq = self.plot_data[-1] if self.plot_data else 0
        self.freq_label.config(text=f"{current_freq} Hz")
        self.ax.clear(); self.ax.plot(list(self.plot_data), 'b-'); self.ax.set_title("Real-time Frequency (Smoothed)"); self.ax.set_ylabel("Hz"); self.ax.set_xticklabels([]); self.canvas.draw()
        if self.is_running: self.root.after(250, self.update_gui)
    def reset_buttons(self):
        self.start_button.config(state=tk.NORMAL); self.duration_entry.config(state=tk.NORMAL); self.stop_button.config(state=tk.DISABLED, text="STOP & Analyze")

if __name__ == "__main__":
    root = tk.Tk()
    app = SawitDetectorApp(root)
    if app.mode:
        root.mainloop()