import os
import pandas as pd
from tkinter import Tk, filedialog

print("==============================================")
print("= Konverter TXT ke CSV untuk Aplikasi Deteksi =")
print("==============================================")

# 1. Buka dialog untuk memilih file .txt sumber
root = Tk()
root.withdraw() # Sembunyikan window utama tkinter

input_files = filedialog.askopenfilenames(
    title="Pilih satu atau beberapa file .txt yang akan dikonversi",
    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
)

# Cek jika pengguna membatalkan pemilihan file
if not input_files:
    print("\nTidak ada file yang dipilih. Program berhenti.")
else:
    all_frequencies = [] # List untuk menampung semua nilai frekuensi
    
    print(f"\nMemproses {len(input_files)} file yang dipilih...")

    # 2. Loop melalui setiap file dan ekstrak HANYA frekuensinya
    for file_path in input_files:
        filename = os.path.basename(file_path)
        print(f" -> Membaca file: {filename}")
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    # Pisahkan berdasarkan ' - '
                    parts = line.strip().split(' - ')
                    if len(parts) == 2:
                        # Ambil bagian kedua (frekuensi)
                        frequency_value = parts[1]
                        # Pastikan nilainya adalah angka sebelum ditambahkan
                        if frequency_value.isdigit():
                            all_frequencies.append(int(frequency_value))
        except Exception as e:
            print(f"   - Gagal membaca file {filename}. Error: {e}")


    # 3. Buat DataFrame dan simpan ke CSV dengan format yang benar
    if not all_frequencies:
        print("\nPERINGATAN: Tidak ada data frekuensi valid yang ditemukan di semua file yang dipilih.")
    else:
        # Buat DataFrame dengan satu kolom bernama 'frekuensi'
        df = pd.DataFrame(all_frequencies, columns=['frekuensi'])
        
        # Tentukan nama file output
        output_filename = "data_konversi_untuk_prediksi.csv"
        df.to_csv(output_filename, index=False)
        
        print("\n========================================================")
        print(f"✅ SUKSES! File '{output_filename}' telah dibuat.")
        print("   File ini sekarang siap digunakan di aplikasi GUI mode Simulasi.")
        print(f"   Total baris data frekuensi yang diekstrak: {len(df)}")
        print("========================================================")