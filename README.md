# Oil Palm Health Detection System

An ultrasonic sensor system for detecting early signs of oil palm disease. The hardware records ultrasonic frequency signals produced by the plant, while the Python application processes the signal and predicts the disease stage.

## System components

- **WisBlock Core RAK4631**: main controller based on the nRF52840 MCU and Semtech SX1262 LoRa transceiver.
- **WisBlock Base Board RAK19007**: connects the Core, sensor modules, USB-C interface, power, and expansion headers.
- **WisBlock Ultrasonic Microphone RAK18032**: captures ultrasonic plant signals through a PDM microphone.
- **USB Type-C cable**: provides power, firmware upload, and serial communication.

### Main hardware specifications

| Component | Key specifications |
| --- | --- |
| RAK4631 | ARM Cortex-M4F, 64 MHz, 1 MB Flash, 256 KB RAM, 2.0-3.6 V supply |
| RAK19007 | 30 x 60 mm, USB-C, battery and solar interfaces, Core and sensor slots |
| RAK18032 | SPH0655LM4H-1, ultrasonic PDM microphone, 20-80 kHz response, 3.3-3.6 V |

## Hardware assembly

1. Prepare the RAK4631 Core, RAK19007 Base Board, and RAK18032 sensor.
2. Check that all components are present and undamaged.
3. Install the RAK4631 in the WisBlock Core slot.
4. Install the RAK18032 in the WisBlock IO slot.
5. Secure the modules carefully with the appropriate M1.2 x 3 mm screws.
6. Connect the device to the computer with a USB Type-C cable.

## Firmware configuration

### Install the RAK4631 board package

1. Install [Arduino IDE](https://www.arduino.cc/en/software).
2. Open **File > Preferences**.
3. Add the following URL to **Additional Boards Manager URLs**:

	```text
	https://raw.githubusercontent.com/RAKwireless/RAKwireless-Arduino-BSP-Index/main/package_rakwireless_index.json
	```

4. Open **Tools > Board > Boards Manager**.
5. Search for `RAK` and install the WisBlock Core package for **RAK4631**.

### Install the audio library

For Arduino IDE 2.0 or later:

1. Open **Sketch > Include Library > Manage Libraries**.
2. Search for `rakwireless`.
3. Install **RAKwireless-Audio-library**.

For older Arduino IDE versions, download the ZIP from the [RAKwireless Audio Library repository](https://github.com/RAKWireless/RAKWireless-Audio-library), then select **Sketch > Include Library > Add .ZIP Library**.

### Upload the firmware

1. Download the firmware examples from [Program-Konfigurasi-Alat](https://github.com/malif2232/Program-Konfigurasi-Alat).
2. Extract the archive and open `HighRatePDMSerialPlotterFFT` in Arduino IDE.
3. Connect the assembled device with USB Type-C.
4. Select the **WisBlock RAK4631** board and the detected serial port.
5. Click **Upload** and wait until the upload completes.
6. Open **Tools > Serial Plotter** to confirm that frequency values are being received.

## Python application

The original manual refers to a packaged Windows executable. This repository provides the equivalent Python application and model files.

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

On Linux, Tkinter may need to be installed separately (`python3-tk`). Serial access may also require membership in the `dialout` group.

### Run the detector

```bash
python Gui.py
```

`Gui.py` supports:

- **Realtime mode**: reads numeric frequency values from the sensor over a serial port.
- **Simulation mode**: loads a CSV file containing a `frekuensi` column.

Place the sensor approximately 2 cm from the oil palm being inspected. The standard recording procedure is approximately three minutes. Stop the recording to display the final prediction and optionally save the captured data.

On Linux, serial devices usually appear as `/dev/ttyUSB0` or `/dev/ttyACM0`. On Windows, use the detected `COM` port.

The enhanced monitoring version, which includes prediction scores and sensor downtime tracking, is available in `deteksi_v3.py`:

```bash
python deteksi_v3.py
```

## Retraining the model

Run this command from the project root:

```bash
python training/train_model.py
```

The training script extracts statistical and wavelet features, applies signal augmentation, and writes updated model files to `models/active/` and evaluation plots to `artifacts/plots/`.

## Maintenance

- Clean the device regularly with a dry cloth.
- Keep the device away from high humidity and direct sunlight.
- Keep the firmware and Arduino libraries up to date.
- Inspect the sensor and Base Board connections if readings stop.

## Troubleshooting

| Problem | Suggested solution |
| --- | --- |
| Device does not power on | Check the USB cable and power source. |
| Sensor produces no frequency values | Reseat the RAK18032 in the Base Board and verify the selected serial port. |
| Python application cannot start | Install `requirements.txt`, verify Tkinter, and check that the model files exist in `models/active/`. |
| Sensor connection fails | Confirm the device is connected, the correct port is selected, and the user has serial-port permissions. |

## References

Abiyyu, Muhammad Alif Nur, and Barlian Henryranu Prasetio, S.T., M.T., Ph.D. (2025). *Penerapan Wavelet Transform pada Sinyal Ultrasound untuk Analisis Kesehatan Bibit Tanaman Sawit*. Sarjana thesis, Universitas Brawijaya. [Repository record](https://repository.ub.ac.id/id/eprint/236964/)