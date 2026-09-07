import os
import csv
from datetime import datetime
from tkinter import Tk, filedialog

# --- FUNGSI UNTUK MENULIS CSV (Tidak perlu diubah) ---
def write_final_csv(all_data, output_file):
    """Fungsi ini hanya bertugas menulis semua data yang terkumpul ke file CSV."""
    if not all_data:
        print("PERINGATAN: Tidak ada data valid yang ditemukan untuk ditulis.")
        return

    with open(output_file, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Tanggal', 'Jam', 'Menit', 'Detik', 'Waktu', 'frekuensi', 'label'])
        csvwriter.writerows(all_data)

    print(f"\n✅ Konversi selesai. File '{output_file}' berhasil dibuat.")
    print(f"Total baris data yang diproses dari semua file: {len(all_data)}")


# --- BAGIAN INTERAKTIF ---
root = Tk()
root.withdraw()

# 1. Pilih SEMUA file .txt yang akan diproses di awal
print("Silakan pilih SEMUA file .txt yang akan diproses (dari tahap 0 hingga 5)...")
input_files = filedialog.askopenfilenames(
    title="Pilih semua file .txt sumber data (tahap 0-5)",
    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
)

if not input_files:
    print("Tidak ada file yang dipilih. Program berhenti.")
else:
    all_data = [] # List kosong untuk menampung semua data dari semua file

    print("\n--- Proses Pelabelan Data ---")
    # 2. Loop melalui setiap file yang sudah dipilih untuk meminta label
    for file_path in input_files:
        filename = os.path.basename(file_path)
        
        # --- PERUBAHAN UTAMA DI SINI ---
        
        # Minta pengguna memasukkan HANYA ANGKA label
        label_angka = input(f"Masukkan HANYA ANGKA label untuk file '{filename}': ").strip()

        if not label_angka or not label_angka.isdigit():
            print(f"  -> Input bukan angka valid, file '{filename}' dilewati.")
            continue

        # Format labelnya dengan menambahkan "Tahap-" di depan
        label_final = f"Tahap-{label_angka}"
        
        # --- AKHIR DARI PERUBAHAN ---

        print(f"  -> Memproses '{filename}' dengan label '{label_final}'...")
        
        # Proses isi file (parsing data)
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    parts = line.strip().split(' - ')
                    if len(parts) == 2:
                        try:
                            dt = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
                            csv_row = [
                                dt.strftime('%m/%d/%Y'),
                                str(dt.hour),
                                str(dt.minute),
                                str(dt.second),
                                dt.strftime('%H:%M:%S'),
                                parts[1],
                                label_final  # <- Menggunakan label yang sudah diformat
                            ]
                            if '0' not in csv_row:
                                all_data.append(csv_row)
                        except (ValueError, IndexError):
                            print(f"    - Format data salah, baris dilewati: {line.strip()}")
        except Exception as e:
            print(f"Gagal membuka atau membaca file: {file_path}. Error: {e}")

    # 3. Setelah semua file diberi label dan diproses, minta nama file output
    print("\n--- Proses Penyimpanan File ---")
    nama_file_custom = input("Masukkan nama untuk file output gabungan (contoh: hasil_final_tahap_0-5): ").strip()

    if not nama_file_custom:
        output_file = f"output_gabungan.csv"
        print(f"Nama file kosong, menggunakan nama default: {output_file}")
    else:
        if not nama_file_custom.lower().endswith('.csv'):
            output_file = f"{nama_file_custom}.csv"
        else:
            output_file = nama_file_custom
            
    # 4. Tulis semua data yang sudah terkumpul ke satu file CSV
    write_final_csv(all_data, output_file)
