import os
import csv
from datetime import datetime

def convert_txt_to_csv(input_folder, output_file, label):
    # Daftar untuk menyimpan semua data
    all_data = []

    # Dapatkan semua file txt di folder
    txt_files = [f for f in os.listdir(input_folder) if f.endswith('.txt')]

    # Proses setiap file
    for txt_file in txt_files:
        file_path = os.path.join(input_folder, txt_file)
        
        with open(file_path, 'r') as f:
            for line in f:
                # Hapus whitespace dan split
                parts = line.strip().split(' - ')
                
                # Pastikan format data benar
                if len(parts) == 2:
                    try:
                        # Parse tanggal
                        dt = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
                        
                        # Format data sesuai kebutuhan
                        csv_row = [
                            dt.strftime('%m/%d/%Y'),  # Tanggal
                            str(dt.hour),             # Jam
                            str(dt.minute),           # Menit
                            str(dt.second),           # Detik
                            dt.strftime('%H:%M:%S'),  # Waktu
                            parts[1],                 # Frekuensi
                            label                     # Label Kesehatan
                        ]

                        # Check if any value in csv_row is '0'
                        if '0' not in csv_row:
                            all_data.append(csv_row)
                    
                    except (ValueError, IndexError) as e:
                        print(f"Error memproses baris: {line.strip()}. Error: {e}")

    # Tulis ke file CSV
    with open(output_file, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Tulis header
        csvwriter.writerow(['Tanggal', 'Jam', 'Menit', 'Detik', 'Waktu', 'frekuensi', 'label'])
        
        # Tulis data
        csvwriter.writerows(all_data)

    print(f"Konversi selesai. Total baris: {len(all_data)}")

# Cara penggunaan
input_folder = 'E:/Kuliah/sem7/sks/Data/tanaman_sehat_gabung'
output_file = 'output_kaca_sehat.csv'
label = 'sehat'  # Label yang ingin ditambahkan

convert_txt_to_csv(input_folder, output_file, label)
