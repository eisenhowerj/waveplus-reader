# MIT License
#
# Copyright (c) 2018 Airthings AS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://airthings.com

# ===============================
# Module import dependencies
# ===============================


from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate
import sys
import time
import struct
from influxdb import InfluxDBClient

INFLUXDB_HOST = '192.168.1.81'
INFLUXDB_DB = 'wavebtle'
INFLUXDB_USER = 'wave-btle'
INFLUXDB_PASS = 'Phoo)chai7'
INFLUXDB_PORT = '8086'
MAC_ADDR = 'A4:DA:32:27:6A:34'
SAMPLE_PERIOD = 10 # Seconds between polls

# ===============================
# Class WavePlus
# ===============================

class WavePlus():
    
    def __init__(self, MAC_ADDR):
        self.periph        = None
        self.curr_val_char = None
        self.MacAddr       = MAC_ADDR
        self.uuid          = UUID("b42e4dcc-ade7-11e4-89d3-123b93f75cba")

    def connect(self):
        # Connect to device
        if (self.periph is None):
            self.periph = Peripheral(self.MacAddr)
        if (self.curr_val_char is None):
            self.curr_val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]
        
    def read(self):
        if (self.curr_val_char is None):
            print("ERROR: Devices are not connected.")
            sys.exit(1)            
        rawdata = self.curr_val_char.read()
        rawdata = struct.unpack('BBBBHHHHHHHH', rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors
    
    def disconnect(self):
        if self.periph is not None:
            self.periph.disconnect()
            self.periph = None
            self.curr_val_char = None

# ===================================
# Class Sensor and sensor definitions
# ===================================

NUMBER_OF_SENSORS               = 4
SENSOR_IDX_HUMIDITY             = 0
SENSOR_IDX_RADON_SHORT_TERM_AVG = 1
SENSOR_IDX_RADON_LONG_TERM_AVG  = 2
SENSOR_IDX_TEMPERATURE          = 3

class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.sensor_data    = [None]*NUMBER_OF_SENSORS
        self.sensor_units   = ["%rH", "Bq/m3", "Bq/m3", "degC"]
    
    def set(self, rawData):
        self.sensor_version = rawData[0]
        if (self.sensor_version == 1):
            self.sensor_data[SENSOR_IDX_HUMIDITY]             = rawData[1]/2.0
            self.sensor_data[SENSOR_IDX_RADON_SHORT_TERM_AVG] = self.conv2radon(rawData[4])
            self.sensor_data[SENSOR_IDX_RADON_LONG_TERM_AVG]  = self.conv2radon(rawData[5])
            self.sensor_data[SENSOR_IDX_TEMPERATURE]          = rawData[6]/100.0

        else:
            print("ERROR: Unknown sensor version.\n")
            sys.exit(1)
   
    def conv2radon(self, radon_raw):
        radon = "N/A" # Either invalid measurement, or not available
        if 0 <= radon_raw <= 16383:
            radon  = radon_raw
        return radon

    def getValue(self, sensor_index):
        return self.sensor_data[sensor_index]

    def getUnit(self, sensor_index):
        return self.sensor_units[sensor_index]

try:
    #---- Initialize ----#
    waveplus = WavePlus(MAC_ADDR)        
    waveplus.connect()
    #---- Connect to InfluxDB ----#
    influx_client = InfluxDBClient(host=INFLUXDB_HOST,
                            port=INFLUXDB_PORT,
                            username=INFLUXDB_USER,
                            password=INFLUXDB_PASS)
    
    # read values
    sensors = waveplus.read()
    
    # extract
    humidity     = str(sensors.getValue(SENSOR_IDX_HUMIDITY))
    radon_st_avg = str(sensors.getValue(SENSOR_IDX_RADON_SHORT_TERM_AVG))
    radon_lt_avg = str(sensors.getValue(SENSOR_IDX_RADON_LONG_TERM_AVG))
    temperature_c  = str(sensors.getValue(SENSOR_IDX_TEMPERATURE))

    temperature = 9.0/5.0 * temperature_c + 32
    data_start_time = int(round(time.time() * 1000))

    data = []
    data.append("{measurement},location={location} humidity={humidity},radon_st_avg={radon_st_avg},radon_lt_avg={radon_lt_avg},temperature={temperature}"
        .format(measurement="waveplus",
                location="basement",
                humidity=humidity,
                radon_st_avg=radon_st_avg,
                radon_lt_avg=radon_lt_avg,
                temperature=temperature))
    print(data)
    influx_client.write_points(data, database=INFLUXDB_DB, batch_size=10000, protocol='line')

    waveplus.disconnect()
                
finally:
    waveplus.disconnect()
