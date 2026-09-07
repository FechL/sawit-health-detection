import tkinter as tk
from tkinter import scrolledtext, messagebox, font, filedialog, ttk
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
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

# --- Label to Score Mapping ---
# Maps the model's output (Tahap-X) to the requested score (0, 1, 3, 5, 7)
LABEL_TO_SCORE = {
    "Tahap-0": 0,
    "Tahap-1": 1,
    "Tahap-2": 3,
    "Tahap-3": 5,
    "Tahap-4": 7
}

# --- Feature Extraction Function ---
def extract_features(data_series):
    """Extracts features from the data series"""
    features = {}
    features['mean'] = data_series.mean()
    features['std_dev'] = data_series.std()
    features['variance'] = data_series.var()
    features['max_val'] = data_series.max()
    features['min_val'] = data_series.min()
    features['skewness'] = data_series.skew()
    features['kurtosis'] = data_series.kurtosis()
    
    # Zero Crossing Rate
    zero_crossings = np.where(np.diff(np.sign(data_series)))[0]
    features['zcr'] = len(zero_crossings) / len(data_series) if len(data_series) > 0 else 0
    
    # Wavelet Energy
    try:
        coeffs = pywt.wavedec(data_series, 'db4', level=4)
        cA4, cD4, cD3, cD2, cD1 = coeffs
        features['energy_d1'] = np.sum(np.square(cD1))
        features['energy_d2'] = np.sum(np.square(cD2))
        features['energy_d3'] = np.sum(np.square(cD3))
        features['energy_d4'] = np.sum(np.square(cD4))
        features['energy_a4'] = np.sum(np.square(cA4))
    except ValueError:
        features['energy_d1'] = features['energy_d2'] = features['energy_d3'] = features['energy_d4'] = features['energy_a4'] = 0
        
    return features

# --- Resource Path Function (for PyInstaller) ---
def get_resource_path(relative_path):
    """Gets the resource path for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = PROJECT_ROOT
    return os.path.join(base_path, relative_path)


def available_serial_ports():
    if sys.platform.startswith("win"):
        return [f"COM{i}" for i in range(1, 21)]
    return [f"/dev/{name}" for name in ("ttyACM0", "ttyACM1", "ttyUSB0", "ttyUSB1")]

# --- Main Application Class ---
class SawitDetectorApp:
    def __init__(self, root):
        # NOTE: Using __init__ instead of _init_
        self.root = root
        self.mode = 'realtime'
            
        self.root.title("Palm Oil Disease Detector - REAL-TIME")
        self.root.geometry("950x850")
        
        self.collection_duration = 120
        self.interim_prediction_interval = 30
        self.max_plot_points = 150
        
        self.model = None
        self.scaler = None
        self.feature_columns = None
        self.ser = None
        self.is_running = False
        self.start_time = 0
        
        # Will store the score (0, 1, 3, 5, or 7)
        self.last_prediction_score = "Ready" 
        
        self.plot_data = deque(maxlen=self.max_plot_points)
        self.all_collected_data = []
        # Structure: [(datetime_obj, raw_freq, prediction_score), ...]
        self.log_data_realtime = [] 
        self.raw_data_buffer = deque(maxlen=5) 
        
        # Sensor health monitoring
        self.last_data_time = None
        self.sensor_timeout = 3
        self.is_sensor_down = False
        self.current_downtime_start = None
        self.total_downtime = 0
        self.downtime_count = 0
        self.paused_time = 0
        
        self.setup_gui()
        self.load_model_and_scaler()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_gui(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        title_font = font.Font(family="Helvetica", size=18, weight="bold")
        status_font = font.Font(family="Helvetica", size=14, weight="bold")
        freq_font = font.Font(family="Helvetica", size=28, weight="bold")
        result_font = font.Font(family="Helvetica", size=16, weight="bold")
        
        tk.Label(self.root, text="Palm Oil Disease Detection Monitoring", font=title_font, pady=10).pack()
        
        # Control frame
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=5)
        
        # COM Port Selector
        tk.Label(control_frame, text="Sensor Port:", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=(10, 5))
        ports = available_serial_ports()
        self.com_port_var = tk.StringVar(value=ports[0])
        self.com_port_combo = ttk.Combobox(control_frame, textvariable=self.com_port_var, 
                            values=ports,
                                            width=8, state='readonly', font=("Helvetica", 11))
        self.com_port_combo.pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(control_frame, text="Duration:", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=(10, 5))
        self.duration_var = tk.StringVar(value="2")
        self.duration_entry = tk.Entry(control_frame, textvariable=self.duration_var, 
                                        font=("Helvetica", 12), width=5)
        self.duration_entry.pack(side=tk.LEFT)
        tk.Label(control_frame, text="minutes", font=("Helvetica", 11)).pack(side=tk.LEFT, padx=(5, 0))
        
        # Plot frame
        plot_frame = tk.Frame(self.root)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Info frame
        info_frame = tk.Frame(self.root, pady=10)
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)
        
        left_frame = tk.Frame(info_frame)
        left_frame.grid(row=0, column=0, sticky="ew")
        self.freq_label = tk.Label(left_frame, text="0 Hz", font=freq_font, fg="navy")
        self.freq_label.pack()
        self.timer_label = tk.Label(left_frame, text="Time: 00:00 / 02:00", font=status_font)
        self.timer_label.pack()
        
        # Downtime indicator
        self.downtime_label = tk.Label(left_frame, text="", font=("Helvetica", 10), fg="red")
        self.downtime_label.pack()
        
        right_frame = tk.Frame(info_frame)
        right_frame.grid(row=0, column=1, sticky="ew")
        self.interim_result_label = tk.Label(right_frame, text="Interim Score: -", font=result_font, fg="gray")
        self.interim_result_label.pack()
        self.final_result_label = tk.Label(right_frame, text="Final Score: Ready", font=status_font, fg="black")
        self.final_result_label.pack()
        
        # Button frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        self.start_button = tk.Button(button_frame, text="START", command=self.click_start_button, 
                                        font=status_font, bg="#4CAF50", fg="white", relief=tk.RAISED)
        self.start_button.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)
        self.stop_button = tk.Button(button_frame, text="STOP & Analyze", command=self.stop_and_analyze, 
                                        font=status_font, bg="#f44336", fg="white", state=tk.DISABLED, relief=tk.RAISED)
        self.stop_button.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)
        
        # Log frame
        log_frame = tk.LabelFrame(self.root, text="Status Log", font=status_font, padx=5, pady=5)
        log_frame.pack(fill=tk.X, expand=False, padx=10, pady=(5, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, state=tk.DISABLED, font=("Courier New", 9))
        self.log_text.pack(fill=tk.X, expand=True)

    def log(self, message):
        """Prints message to console and updates the GUI log box"""
        print(message)
        def append_log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append_log)

    def connect_to_port(self, port):
        """Connects to the selected serial port"""
        # ... (unchanged) ...
        try:
            self.log(f"Attempting to connect to {port}...")
            temp_ser = serial.Serial(port, 9600, timeout=2)
            time.sleep(2) 
            
            if temp_ser.in_waiting > 0:
                line = temp_ser.readline().decode('utf-8').strip()
                if not line:
                    self.log(f"-> {port} is open, but sending no data.")
                    temp_ser.close()
                    return False
                
                int(line)  # Validate numeric data
                self.ser = temp_ser
                self.ser.reset_input_buffer()
                self.log(f"✅ Successfully connected to {port}!")
                self.root.after(0, lambda: self.final_result_label.config(text=f"Connected: {port}", fg="green"))
                return True
            else:
                self.log(f"-> {port} is open but no data is received.")
                temp_ser.close()
                return False
                
        except serial.SerialException as e:
            self.log(f"-> Failed to open {port}: {e}")
            return False
        except (ValueError, UnicodeDecodeError):
            self.log(f"-> {port} is sending invalid data (not a number).")
            if temp_ser and temp_ser.is_open:
                temp_ser.close()
            return False

    def click_start_button(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        try:
            duration_minutes = float(self.duration_var.get())
            if duration_minutes <= 0:
                raise ValueError
            self.collection_duration = int(duration_minutes * 60)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a positive number for duration.")
            return
        
        self.start_button.config(state=tk.DISABLED)
        self.duration_entry.config(state=tk.DISABLED)
        self.com_port_combo.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.plot_data.clear()
        self.all_collected_data = []
        self.log_data_realtime = []
        self.raw_data_buffer.clear()
        self.last_prediction_score = "Ready" # Reset score
        
        # Reset sensor monitoring
        self.last_data_time = None
        self.is_sensor_down = False
        self.current_downtime_start = None
        self.total_downtime = 0
        self.downtime_count = 0
        self.paused_time = 0
        
        self._start_monitoring_thread()

    def on_closing(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    def make_final_prediction(self):
        self.final_result_label.config(text="Analyzing all data...", fg="blue")
        self.root.update()
        
        if self.total_downtime > 0:
            self.log(f"\n📊 DOWNTIME SUMMARY:")
            self.log(f"    • Total incidents: {self.downtime_count} times")
            self.log(f"    • Total duration: {self.total_downtime:.1f} seconds")
            self.log(f"    • Timer effect: Paused during downtime\n")
        
        # Get the predicted label (e.g., "Tahap-3")
        predicted_label = self._predict_from_data(self.all_collected_data)

        if predicted_label:
            # --- MODIFICATION 1: Convert label to score for display ---
            final_score = LABEL_TO_SCORE.get(predicted_label, 'N/A')
            self.last_prediction_score = final_score

            color = "red" if final_score > 0 else "green"
            self.final_result_label.config(text=f"Final Score: {final_score}", fg=color)
            
            result_msg = f"Based on the data analysis, the final detection score is:\n\nScore: {final_score} (Stage: {predicted_label})"
            if self.total_downtime > 0:
                result_msg += f"\n\n⚠ Note: Sensor experienced {self.downtime_count} downtime incidents ({self.total_downtime:.0f} seconds)"
            
            messagebox.showinfo("Analysis Complete", result_msg)
        else:
            self.last_prediction_score = "N/A"
            self.final_result_label.config(text="Analysis Failed (Insufficient Data)", fg="red")
            messagebox.showwarning("Warning", "Too little data was recorded for accurate analysis.")
            
        # Ask to save data
        if self.log_data_realtime:
            self.save_data_to_csv(self.last_prediction_score)

        self.reset_buttons()

    def monitoring_loop_realtime(self):
        # ... (mostly unchanged, key part is how data is logged) ...
        selected_port = self.com_port_var.get()
        if not self.connect_to_port(selected_port):
            messagebox.showerror("Connection Failed", f"Cannot connect to {selected_port}!\n\nPlease ensure:\n• Correct Port\n• Sensor is connected\n• Drivers are installed")
            self.is_running = False
            self.root.after(0, self.reset_buttons)
            return
        
        self.start_time = time.time()
        self.last_data_time = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 20
        
        while self.is_running:
            try:
                current_time = time.time()
                current_dt = datetime.now()
                
                # Check sensor timeout and handle downtime
                time_since_last_data = current_time - self.last_data_time
                
                if time_since_last_data > self.sensor_timeout:
                    # ... (downtime logic) ...
                    if not self.is_sensor_down:
                        self.is_sensor_down = True
                        self.current_downtime_start = current_time
                        self.downtime_count += 1
                        self.log(f"⚠ SENSOR DOWN! (Incident #{self.downtime_count})")
                        self.root.after(0, lambda: self.final_result_label.config(
                            text=f"⚠ Sensor Disconnected!", fg="red"))
                    
                    current_downtime = current_time - self.current_downtime_start
                    self.root.after(0, lambda dt=current_downtime: self.downtime_label.config(
                        text=f"🔴 Downtime: {dt:.1f} seconds", fg="red"))
                    
                # Read data from serial
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line:
                        raw_freq = int(line)
                        
                        if self.is_sensor_down:
                            # ... (sensor back to normal logic) ...
                            downtime_duration = current_time - self.current_downtime_start
                            self.total_downtime += downtime_duration
                            self.paused_time += downtime_duration
                            self.log(f"✅ Sensor back to normal! (Down for {downtime_duration:.1f} seconds)")
                            self.is_sensor_down = False
                            self.current_downtime_start = None
                            self.root.after(0, lambda: self.downtime_label.config(text=""))
                            self.root.after(0, lambda: self.final_result_label.config(
                                text="Sensor Normal", fg="green"))
                        
                        self.last_data_time = current_time
                        consecutive_errors = 0
                        
                        # Process data
                        self.raw_data_buffer.append(raw_freq)
                        smoothed_freq = int(np.mean(self.raw_data_buffer))
                        
                        self.plot_data.append(smoothed_freq)
                        self.all_collected_data.append(smoothed_freq)
                        
                        # --- MODIFICATION 2: Log the score instead of the label ---
                        self.log_data_realtime.append((current_dt, raw_freq, self.last_prediction_score))

                        self.check_for_interim_prediction()
                    else:
                        time.sleep(0.05)
                        
            except (ValueError, serial.SerialException, UnicodeDecodeError) as e:
                # ... (error handling) ...
                consecutive_errors += 1
                self.log(f"Error reading data ({consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.log(f"❌ Too many consecutive errors! Stopping monitoring.")
                    self.is_running = False
                    self.root.after(0, lambda: messagebox.showerror(
                        "Sensor Error", 
                        f"Sensor experienced too many errors!\n\nMonitoring stopped."))
                    break
                
                time.sleep(0.5)
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.after(0, self.make_final_prediction)

    def load_model_and_scaler(self):
        # ... (unchanged) ...
        try:
            model_path = get_resource_path('models/active/model_terbaik_augmented.joblib')
            scaler_path = get_resource_path('models/active/scaler_augmented.joblib')
            
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            
            feature_col_path = get_resource_path('feature_columns.joblib')
            if os.path.exists(feature_col_path):
                self.feature_columns = joblib.load(feature_col_path)
                self.log("Feature columns loaded successfully from file.")
            elif hasattr(self.scaler, 'feature_names_in_'):
                self.feature_columns = list(self.scaler.feature_names_in_)
                self.log("Feature columns taken from scaler.feature_names_in_")
            else:
                self.feature_columns = ['mean', 'std_dev', 'variance', 'max_val', 'min_val', 
                                        'skewness', 'kurtosis', 'zcr', 'energy_d1', 'energy_d2', 
                                        'energy_d3', 'energy_d4', 'energy_a4']
                self.log("⚠ Using default feature order (may not be accurate)")
            
            self.log("Model and Scaler loaded successfully.")
            return True
        except Exception as e:
            self.log(f"Critical Error: Failed to load model/scaler! Error: {e}")
            messagebox.showerror("Critical Error", 
                                f"Failed to load model/scaler!\nPlease ensure model files exist.\n\nError: {e}")
            self.root.quit()
            return False

    def _start_monitoring_thread(self):
        self.is_running = True
        self.final_result_label.config(text="Starting process...", fg="orange")
        
        self.monitor_thread = threading.Thread(target=self.monitoring_loop_realtime, daemon=True)
        self.monitor_thread.start()
        self.update_gui()

    def stop_and_analyze(self):
        if self.is_running:
            self.is_running = False
            self.stop_button.config(state=tk.DISABLED, text="Analyzing...")
            self.log("Process stopped by user, proceeding to analysis.")

    def check_for_interim_prediction(self):
        current_time = time.time()
        if not hasattr(self, 'last_interim_time'):
            self.last_interim_time = self.start_time
        
        effective_time = (current_time - self.start_time) - self.paused_time
        
        if current_time - self.last_interim_time > self.interim_prediction_interval:
            self.last_interim_time = current_time
            threading.Thread(target=self.make_interim_prediction, daemon=True).start()
        
        if effective_time >= self.collection_duration:
            self.is_running = False

    def _predict_from_data(self, data):
        """Returns the predicted label (e.g., 'Tahap-0') from the model."""
        if len(data) < 256:
            return None
        
        all_features_list = []
        window_size = 256
        step = 32
        
        for i in range(0, len(data) - window_size + 1, step):
            window = data[i : i + window_size]
            if len(window) == window_size:
                all_features_list.append(extract_features(pd.Series(window)))
        
        if not all_features_list:
            return None
        
        df_features = pd.DataFrame(all_features_list).fillna(0)
        
        if self.feature_columns and set(self.feature_columns).issubset(df_features.columns):
            df_features = df_features[self.feature_columns]
        else:
            self.log("⚠ WARNING: Feature columns mismatch or missing. Proceeding with available features.")
            
        X_scaled = self.scaler.transform(df_features)
        predictions = self.model.predict(X_scaled)
        
        return pd.Series(predictions).mode()[0] # Returns the most frequent label (e.g., "Tahap-3")

    def make_interim_prediction(self):
        # Get the predicted label (e.g., "Tahap-3")
        predicted_label = self._predict_from_data(self.all_collected_data[-512:])
        if predicted_label:
            # --- MODIFICATION 3: Convert label to score for display and logging ---
            interim_score = LABEL_TO_SCORE.get(predicted_label, 'N/A')
            self.last_prediction_score = interim_score # Update last known score
            
            self.root.after(0, lambda: self.interim_result_label.config(
                text=f"Interim Score: {interim_score}", fg="darkorange"))

    def update_gui(self):
        # ... (timer update logic unchanged) ...
        if self.is_running and self.start_time > 0:
            current_time = time.time()
            
            if self.is_sensor_down and self.current_downtime_start:
                elapsed_seconds = int((self.current_downtime_start - self.start_time) - self.paused_time)
            else:
                elapsed_seconds = int((current_time - self.start_time) - self.paused_time)
            
            total_minutes, _ = divmod(self.collection_duration, 60)
            minutes, seconds = divmod(elapsed_seconds, 60)
            
            timer_color = "red" if self.is_sensor_down else "black"
            self.timer_label.config(
                text=f"Time: {minutes:02d}:{seconds:02d} / {int(total_minutes):02d}:00 {'⏸' if self.is_sensor_down else ''}",
                fg=timer_color
            )
        
        current_freq = self.plot_data[-1] if self.plot_data else 0
        self.freq_label.config(text=f"{current_freq} Hz")
        
        # Update plot
        self.ax.clear()
        self.ax.plot(list(self.plot_data), 'b-')
        self.ax.set_title("Real-time Frequency Graph (Smoothed)")
        self.ax.set_ylabel("Hz")
        self.ax.set_xticks([])
        self.canvas.draw()
        
        if self.is_running:
            self.root.after(250, self.update_gui)

    def reset_buttons(self):
        self.start_button.config(state=tk.NORMAL)
        self.duration_entry.config(state=tk.NORMAL)
        self.com_port_combo.config(state='readonly')
        self.stop_button.config(state=tk.DISABLED, text="STOP & Analyze")
        self.downtime_label.config(text="")

    def save_data_to_csv(self, final_score):
        """Saves the logged data to a CSV file with the requested format."""
        
        # Get the score to be used for the 'label' column (now 'score')
        score_to_use = final_score 
        if score_to_use in ["Ready", "Analysis Failed", "Sensor Normal", "-", "N/A"]:
            score_to_use = 'N/A' # Default for invalid/unset score
        
        data_for_df = [
            {
                'Tanggal': dt.strftime('%m/%d/%Y'),
                'Jam': dt.hour,
                'Menit': dt.minute,
                'Detik': dt.second,
                'Waktu': dt.strftime('%H:%M:%S'),
                'frekuensi': freq,
                'label': score # Use the logged score
            }
            for dt, freq, score in self.log_data_realtime
        ]
            
        if not data_for_df:
            self.log("No data to save.")
            return

        answer = messagebox.askyesno("Save Data", "Do you want to save the recorded data to a CSV file?")
        if answer:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filepath = filedialog.asksaveasfilename(
                initialfile=f"palm_detector_log_{timestamp}.csv",
                defaultextension=".csv",
                filetypes=[("CSV files", ".csv"), ("All files", ".*")]
            )
            
            if filepath:
                try:
                    df_log = pd.DataFrame(data_for_df)
                    # Rename 'label' column to 'score' for clarity in the file, 
                    # but keeping 'label' in code for minimal disruption
                    df_log.rename(columns={'label': 'score'}, inplace=True) 
                    
                    # Reorder columns as requested (using 'score' as the last column)
                    df_log = df_log[['Tanggal', 'Jam', 'Menit', 'Detik', 'Waktu', 'frekuensi', 'score']]
                    df_log.to_csv(filepath, index=False)
                    self.log(f"Data successfully saved to: {filepath}")
                    messagebox.showinfo("Success", f"Recorded data successfully saved as\n{os.path.basename(filepath)}")
                except Exception as e:
                    self.log(f"Failed to save file: {e}")
                    messagebox.showerror("Failed", f"An error occurred while saving the file:\n{e}")

# --- Main Execution ---
if __name__ == "__main__":
    try:
        import matplotlib
        matplotlib.use('TkAgg')
    except ImportError:
        print("Matplotlib not found. Please install it with 'pip install matplotlib'.")
        sys.exit(1)
        
    root = tk.Tk()
    app = SawitDetectorApp(root)
    root.mainloop()