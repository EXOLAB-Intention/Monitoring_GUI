import serial
import serial.tools.list_ports
import csv
import h5py
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
# import threading


# Use LaTeX font 
# plt.rc('text', usetex=True)
# plt.rc('font', family='serif')


################# [Predefined Information] #################
DATA_CONV_CONST_UINT16            =  65535       # uint16 conversion constant
DATA_CONV_CONST_INT16             =  32767       # int16 conversion constant	
EMG_NORM_SCALING_FACTOR			  =	 1			# Normalized EMG [0,1]
IMU_QUATERNION_SCALING_FACTOR	  =	 2			# [-1,1]
TIMESTAMP_SCALING_FACTOR          =  1

USB_CDC_PROTOCOL_DATA		=	b'\xAB' 	# First transmission of Protocol Data Set
USB_CDC_START_DATA			=	b'\xAC' 	# SOL 
USB_CDC_END_DATA			=	b'\xAD'	    # EOL 
USB_CDC_TERMINATE_PYTHON	=	b'\x4E'          # Should be matched with STM32 FW (b'\x4E = 78)

DataSet = {
    'DS_TIMESTAMP'        : (0, TIMESTAMP_SCALING_FACTOR), 

	'DS_IMU1_QUATERNION_W': (1, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU1_QUATERNION_X': (2, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU1_QUATERNION_Y': (3, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU1_QUATERNION_Z': (4, IMU_QUATERNION_SCALING_FACTOR),

	'DS_IMU2_QUATERNION_W': (5, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU2_QUATERNION_X': (6, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU2_QUATERNION_Y': (7, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU2_QUATERNION_Z': (8, IMU_QUATERNION_SCALING_FACTOR),

	'DS_IMU3_QUATERNION_W': (9, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU3_QUATERNION_X': (10, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU3_QUATERNION_Y': (11, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU3_QUATERNION_Z': (12, IMU_QUATERNION_SCALING_FACTOR),

	'DS_IMU4_QUATERNION_W': (13, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU4_QUATERNION_X': (14, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU4_QUATERNION_Y': (15, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU4_QUATERNION_Z': (16, IMU_QUATERNION_SCALING_FACTOR),

    'DS_IMU5_QUATERNION_W': (17, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU5_QUATERNION_X': (18, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU5_QUATERNION_Y': (19, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU5_QUATERNION_Z': (20, IMU_QUATERNION_SCALING_FACTOR),

    'DS_IMU6_QUATERNION_W': (21, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU6_QUATERNION_X': (22, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU6_QUATERNION_Y': (23, IMU_QUATERNION_SCALING_FACTOR),
	'DS_IMU6_QUATERNION_Z': (24, IMU_QUATERNION_SCALING_FACTOR),

	'DS_EMGL1_NORM'       : (25, EMG_NORM_SCALING_FACTOR),
	'DS_EMGL2_NORM'       : (26, EMG_NORM_SCALING_FACTOR),
	'DS_EMGL3_NORM'       : (27, EMG_NORM_SCALING_FACTOR),
	'DS_EMGL4_NORM'       : (28, EMG_NORM_SCALING_FACTOR),
	'DS_EMGR1_NORM'       : (29, EMG_NORM_SCALING_FACTOR),
	'DS_EMGR2_NORM'       : (30, EMG_NORM_SCALING_FACTOR),
	'DS_EMGR3_NORM'       : (31, EMG_NORM_SCALING_FACTOR),
	'DS_EMGR4_NORM'       : (32, EMG_NORM_SCALING_FACTOR),
}


DataType = {
    'DT_CHAR'       : 0,
	'DT_UINT8'      : 1,
	'DT_UINT16'     : 2,
	'DT_UINT32'     : 3,
	'DT_INT8'       : 4,
	'DT_INT16'      : 5,
	'DT_INT32'      : 6,
	'DT_FLOAT32'    : 7,
	'DT_FLOAT64'    : 8,
	'DT_STRING10'   : 9,
}


################### Class for Data Communication for USB CDC ###################

class DataProtocol:
    def __init__(self):
        self.baudRate_USBCDC = 921600   # Can be changed
        self.serialPort = self.FindSerialPort()
        self.dataName = []
        self.originalDataType = []
        self.scaledDataType = []
        self.decodedData = []
        self.dataProtocolNum = 0        # 3N
        self.rxDataNum = 0              # N
        self.rxDataByte = 0             # Except for SOL and EOL (Total Byte Size of received data)
        self.csvBaseName = './data'
        self.csvFileName = ''
        self.csvWriter = None
        self.csvFile = None
        self.hdf5BaseName = './data'
        self.hdf5FileName = ''
        self.hdf5File = None
        self.labelingOn = False
        self.keyboard = 0               # 1: sit, 2: stand, 3: level walking... (for Labeling)


    
    def FindSerialPort(self):
        serialPort_list = serial.tools.list_ports.comports()
        for port in serialPort_list:
            if port.manufacturer and "STMicroelectronics" in port.manufacturer:
                try:
                    print(f"SUCCESS: Connection to {port.device}")
                    return serial.Serial(port.device, self.baudRate_USBCDC, timeout=1)
                except serial.SerialException as e:
                    print(f"FAIL: Cannot connect to {port.device}: {e}")
        return None
    

    def ReadSensorDetection(self):
        while True:
            if self.serialPort.in_waiting > 0:
                msg = self.serialPort.readline().decode('utf-8').strip()
                print(msg)
                break
    

    def ReadDataProtocol(self, startByte=USB_CDC_PROTOCOL_DATA, endByte=USB_CDC_END_DATA):
        buffer = []

        while True:
            if self.serialPort.in_waiting > 0:
                dataByte = self.serialPort.read(1)
                buffer.append(dataByte)

                if (buffer[0] == startByte and buffer[self.dataProtocolNum] == endByte):
                    self.rxDataByte = int.from_bytes(buffer[self.dataProtocolNum-1], byteorder = 'big')
                    break
                self.dataProtocolNum += 1

        self.dataProtocolNum -= 2    # Remove SOL and EOL
        buffer = buffer[1:-2]

        if (self.dataProtocolNum % 3 != 0):
            print("ERROR!!: Data Protocol is not proper")
            return
        else:
            self.rxDataNum = self.dataProtocolNum // 3
            for idx, element in enumerate(buffer):
                if (idx % 3 == 0):
                    self.dataName.append(element)
                elif (idx % 3 == 1):
                    self.originalDataType.append(element)
                elif (idx % 3 == 2):
                    self.scaledDataType.append(element)


    def ParseDataSet(self):
        for i in range(self.rxDataNum):
            for key, value in DataSet.items():
                if self.dataName[i] == value[0].to_bytes(1, 'big'):
                    self.dataName[i] = key
            for key, value in DataType.items():
                if self.originalDataType[i] == value.to_bytes(1, 'big'):
                    self.originalDataType[i] = key
                if self.scaledDataType[i] == value.to_bytes(1, 'big'):
                    self.scaledDataType[i] = key
        
        # Print ALL DataSet #
        print(f"{'Data Name':^30} \t {'Original Type':^20} \t {'Scaled Type':^20}")
        for item1, item2, item3 in zip(self.dataName, self.originalDataType, self.scaledDataType):
            print(f"{item1:<30} \t {item2:<20} \t {item3:<20}")
        
        print(f"Total Received Data Bytes: {self.rxDataByte}")


    def OpenCSVtoWrite(self):
        counter = 1
        fileFormat = '.csv' 
        self.csvFileName = f"{self.csvBaseName}{counter}{fileFormat}"
        while os.path.exists(self.csvFileName):
            counter += 1
            self.csvFileName = f"{self.csvBaseName}{counter}{fileFormat}"

        self.csvFile = open(self.csvFileName, mode='w', newline='')
        self.csvWriter = csv.writer(self.csvFile)
        

    def WriteCSVHeader(self):
        self.csvWriter.writerow(self.dataName)


    def OpenHDF5toWrite(self):
        counter = 1
        fileFormat = '.h5'
        self.hdf5FileName = f"{self.hdf5BaseName}{counter}{fileFormat}"
        while os.path.exists(self.hdf5FileName):
            counter += 1
            self.hdf5FileName = f"{self.hdf5BaseName}{counter}{fileFormat}"

        self.hdf5File = h5py.File(self.hdf5FileName,'w')

    def CreateHDF5Group(self):
        self.sensor_grp = self.hdf5File.create_group("Sensor")

        self.time_grp = self.hdf5File.create_group("Sensor/Time")
        self.time_data = self.time_grp.create_dataset("time", shape=(0, ), maxshape=(None, ), dtype='i')

        self.imu_grp = self.hdf5File.create_group("Sensor/IMU")
        self.imu1_data = self.imu_grp.create_dataset("imu1", shape=(0, 4), maxshape=(None, 4), dtype='f')
        self.imu2_data = self.imu_grp.create_dataset("imu2", shape=(0, 4), maxshape=(None, 4), dtype='f')
        self.imu3_data = self.imu_grp.create_dataset("imu3", shape=(0, 4), maxshape=(None, 4), dtype='f')
        self.imu4_data = self.imu_grp.create_dataset("imu4", shape=(0, 4), maxshape=(None, 4), dtype='f')
        self.imu5_data = self.imu_grp.create_dataset("imu5", shape=(0, 4), maxshape=(None, 4), dtype='f')
        self.imu6_data = self.imu_grp.create_dataset("imu6", shape=(0, 4), maxshape=(None, 4), dtype='f')

        self.emg_grp = self.hdf5File.create_group("Sensor/EMG")
        self.emgL1_data = self.emg_grp.create_dataset("emgL1", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgL2_data = self.emg_grp.create_dataset("emgL2", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgL3_data = self.emg_grp.create_dataset("emgL3", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgL4_data = self.emg_grp.create_dataset("emgL4", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgR1_data = self.emg_grp.create_dataset("emgR1", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgR2_data = self.emg_grp.create_dataset("emgR2", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgR3_data = self.emg_grp.create_dataset("emgR3", shape=(0, ), maxshape=(None, ), dtype='f')
        self.emgR4_data = self.emg_grp.create_dataset("emgR4", shape=(0, ), maxshape=(None, ), dtype='f')

        self.label_group = self.hdf5File.create_group("Sensor/LABEL")
        self.label_data = self.label_group.create_dataset("label", shape=(0, ), maxshape=(None, ), dtype='i')

        self.mapping = {
                'DS_TIMESTAMP'        : [self.time_data,0], 

                'DS_IMU1_QUATERNION_W': [self.imu1_data,0],
                'DS_IMU1_QUATERNION_X': [self.imu1_data,1],
                'DS_IMU1_QUATERNION_Y': [self.imu1_data,2],
                'DS_IMU1_QUATERNION_Z': [self.imu1_data,3],

                'DS_IMU2_QUATERNION_W': [self.imu2_data,0],
                'DS_IMU2_QUATERNION_X': [self.imu2_data,1],
                'DS_IMU2_QUATERNION_Y': [self.imu2_data,2],
                'DS_IMU2_QUATERNION_Z': [self.imu2_data,3],

                'DS_IMU3_QUATERNION_W': [self.imu3_data,0],
                'DS_IMU3_QUATERNION_X': [self.imu3_data,1],
                'DS_IMU3_QUATERNION_Y': [self.imu3_data,2],
                'DS_IMU3_QUATERNION_Z': [self.imu3_data,3],

                'DS_IMU4_QUATERNION_W': [self.imu4_data,0],
                'DS_IMU4_QUATERNION_X': [self.imu4_data,1],
                'DS_IMU4_QUATERNION_Y': [self.imu4_data,2],
                'DS_IMU4_QUATERNION_Z': [self.imu4_data,3],

                'DS_IMU5_QUATERNION_W': [self.imu5_data,0],
                'DS_IMU5_QUATERNION_X': [self.imu5_data,1],
                'DS_IMU5_QUATERNION_Y': [self.imu5_data,2],
                'DS_IMU5_QUATERNION_Z': [self.imu5_data,3],

                'DS_IMU6_QUATERNION_W': [self.imu6_data,0],
                'DS_IMU6_QUATERNION_X': [self.imu6_data,1],
                'DS_IMU6_QUATERNION_Y': [self.imu6_data,2],
                'DS_IMU6_QUATERNION_Z': [self.imu6_data,3],

                'DS_EMGL1_NORM'       : [self.emgL1_data,0],
                'DS_EMGL2_NORM'       : [self.emgL2_data,0],
                'DS_EMGL3_NORM'       : [self.emgL3_data,0],
                'DS_EMGL4_NORM'       : [self.emgL4_data,0],
                'DS_EMGR1_NORM'       : [self.emgR1_data,0],
                'DS_EMGR2_NORM'       : [self.emgR2_data,0],
                'DS_EMGR3_NORM'       : [self.emgR3_data,0],
                'DS_EMGR4_NORM'       : [self.emgR4_data,0]
        }


    def ProcessRxData(self, dataList):
        cursor = 0
        value = 0
        for idx in range(self.rxDataNum):
            if (self.originalDataType[idx] == 'DT_UINT32' and self.scaledDataType[idx] == 'DT_UINT32'):
                value = int.from_bytes(dataList[cursor:cursor+4], byteorder='big')
                cursor += 4
            elif (self.originalDataType[idx] == 'DT_FLOAT32' and self.scaledDataType[idx] == 'DT_UINT16'):
                value = float(int.from_bytes(dataList[cursor:cursor+2], byteorder='big'))
                cursor += 2
            elif (self.originalDataType[idx] == 'DT_FLOAT32' and self.scaledDataType[idx] == 'DT_INT16'):
                value = float(int.from_bytes(dataList[cursor:cursor+2], byteorder='big', signed=True))
                cursor += 2

            self.decodedData.append(value)

    
    def ScalingRxData(self, processedDataList):
        dataConvScaler = 1
        for idx in range(self.rxDataNum):
            scaleFactor = DataSet[self.dataName[idx]][1]
            if (self.originalDataType[idx] == 'DT_UINT32' and self.scaledDataType[idx] == 'DT_UINT32'):
                dataConvScaler = 1
            elif (self.originalDataType[idx] == 'DT_FLOAT32' and self.scaledDataType[idx] == 'DT_UINT16'):
                dataConvScaler = DATA_CONV_CONST_UINT16
            elif (self.originalDataType[idx] == 'DT_FLOAT32' and self.scaledDataType[idx] == 'DT_INT16'):
                dataConvScaler = DATA_CONV_CONST_INT16

            processedDataList[idx] = processedDataList[idx] * scaleFactor / dataConvScaler
    

    def ReadDataSequenceCSV(self, startByte, endByte, terminateByte, dataSave):
        try:
            while True:
                startCheck = self.serialPort.read(1)
                if (startCheck == startByte):
                    if self.serialPort.in_waiting >= (self.rxDataByte + 1):
                        temp = self.serialPort.read(self.rxDataByte + 1)        # EOL
                        if (temp[-1:] == endByte):
                            self.decodedData = []                               # Reset the buffer
                            temp = temp[:self.rxDataByte] 
                            self.ProcessRxData(temp)
                            self.ScalingRxData(self.decodedData)
                            print(self.decodedData)
                            
                            if (dataSave == True):
                                self.csvWriter.writerow(self.decodedData)
                        else:
                            print("ERROR!!: Invalid Data is received")

                elif (startCheck == terminateByte):
                    self.serialPort.close()
                    self.csvFile.close()
                    print("Terminate DAQ")
                    print("Data is saved")
                    break                        

        except KeyboardInterrupt:
            self.serialPort.close()
            self.csvFile.close()
            print("Exit the program. Close the CSV file")

            
        except serial.SerialException as e:
            print(f"SerialException: {e}")

        finally:
            self.serialPort.close()
            self.csvFile.close()



    def ReadDataSequenceHDF5(self, startByte, endByte, terminateByte, dataSave):
        try:
            while True:
                startCheck = self.serialPort.read(1)
                if (startCheck == startByte):
                    if self.serialPort.in_waiting >= (self.rxDataByte + 1):
                        temp = self.serialPort.read(self.rxDataByte + 1)        # EOL
                        if (temp[-1:] == endByte):
                            self.decodedData = []                               # Reset the buffer
                            temp = temp[:self.rxDataByte] 
                            self.ProcessRxData(temp)
                            self.ScalingRxData(self.decodedData)
                            print(self.decodedData)         # 시간 너무 오래걸리면 이 부분 주석처리
                                     
                            if dataSave:
                                resized_set = set()         # resize 한 dset 저장용

                                for i, name in enumerate(self.dataName):
                                    if name in self.mapping:
                                        dset, col_idx = self.mapping[name]

                                        if dset not in resized_set:
                                            curr_len = dset.shape[0]
                                            dset.resize((curr_len + 1), axis=0)
                                            resized_set.add(dset)
                                        else:
                                            curr_len = dset.shape[0] - 1        # 이미 resize 했으면 바로 이전 row가 타겟

                                        if len(dset.shape) == 2:    # imu
                                            dset[curr_len, col_idx] = self.decodedData[i]
                                        else:                       # emg or time (1D)
                                            dset[curr_len] = self.decodedData[i]            

                        else:
                            print("ERROR!!: Invalid Data is received")

                elif (startCheck == terminateByte):
                    self.serialPort.close()
                    self.hdf5File.close()
                    print("Terminate DAQ")
                    print("Data is saved")
                    break                        

        except KeyboardInterrupt:
            self.serialPort.close()
            self.hdf5File.close()
            print("Exit the program. Close the CSV file")

            
        except serial.SerialException as e:
            print(f"SerialException: {e}")

        finally:
            self.serialPort.close()
            self.hdf5File.close()


    # def PlotGraph(self, dataToShow):
    #     data = pd.read_csv(self.csvFileName, header=0)

    #     plt.figure(figsize=(14,8), dpi=120)
    #     plt.plot(data['Time[ms]'], data['EMG_Raw'], label='EMG_Raw', color='b')
    #     plt.xlabel('Time[ms]', fontsize=15)
    #     plt.ylabel('% MVIC', fontsize=15)
    #     plt.ylim(-1, 1)
    #     plt.title('Result of UART TEST', fontsize=25)
    #     plt.grid(alpha=0.4)
    #     plt.legend(loc=1, fontsize=15)
    #     plt.savefig('UART_TEST_1NE.png')  
    #     plt.show()


    # def keyboard_listener(self):
    #     while self.labelingOn:
    #         self.keyboard = input()

    # def ReadDataSequenceHDF5_labeling(self, startByte, endByte, terminateByte, dataSave):
    #     self.labelingOn = True
    #     threading.Thread(target=self.keyboard_listener, daemon=True).start()

    #     try:
    #         while True:
    #             startCheck = self.serialPort.read(1)
    #             if (startCheck == startByte):
    #                 if self.serialPort.in_waiting >= (self.rxDataByte + 1):
    #                     temp = self.serialPort.read(self.rxDataByte + 1)        # EOL
    #                     if (temp[-1:] == endByte):
    #                         self.decodedData = []                               # Reset the buffer
    #                         temp = temp[:self.rxDataByte] 
    #                         self.ProcessRxData(temp)
    #                         self.ScalingRxData(self.decodedData)
    #                         print(self.decodedData)
                                        
    #                         if dataSave:
    #                             resized_set = set()         # resize 한 dset 저장용

    #                             for i, name in enumerate(self.dataName):
    #                                 if name in self.mapping:
    #                                     dset, col_idx = self.mapping[name]

    #                                     if dset not in resized_set:
    #                                         curr_len = dset.shape[0]
    #                                         dset.resize((curr_len + 1), axis=0)
    #                                         resized_set.add(dset)
    #                                     else:
    #                                         curr_len = dset.shape[0] - 1        # 이미 resize 했으면 바로 이전 row가 타겟

    #                                     if len(dset.shape) == 2:    # imu
    #                                         dset[curr_len, col_idx] = self.decodedData[i]
    #                                     else:                       # emg or time (1D)
    #                                         dset[curr_len] = self.decodedData[i]     

    #                             # Labeling part #
    #                             dset_label = self.label_data

    #                             if dset_label not in resized_set:
    #                                 curr_len_label = dset_label.shape[0]
    #                                 dset_label.resize((curr_len_label + 1), axis=0)
    #                                 resized_set.add(dset_label)
    #                             else:
    #                                 curr_len_label = dset_label.shape[0] - 1
    #                             dset_label[curr_len_label] = self.keyboard

                                       

    #                     else:
    #                         print("ERROR!!: Invalid Data is received")

    #             elif (startCheck == terminateByte):
    #                 self.serialPort.close()
    #                 self.hdf5File.close()
    #                 self.labelingOn = False
    #                 print("Terminate DAQ")
    #                 print("Data is saved")
    #                 break                        

    #     except KeyboardInterrupt:
    #         self.serialPort.close()
    #         self.hdf5File.close()
    #         print("Exit the program. Close the CSV file")

            
    #     except serial.SerialException as e:
    #         print(f"SerialException: {e}")

    #     finally:
    #         self.serialPort.close()
    #         self.hdf5File.close()


def main(ars=None):
    ##########################################################################################################################################################

    # Initialization #
    dataObj = DataProtocol()
    dataObj.ReadSensorDetection()
    dataObj.ReadDataProtocol()
    dataObj.ParseDataSet()

    ##########################################################################################################################################################

    # [1] csv version #
    # dataObj.OpenCSVtoWrite()
    # dataObj.WriteCSVHeader()
    # dataObj.ReadDataSequenceCSV(USB_CDC_START_DATA, USB_CDC_END_DATA, USB_CDC_TERMINATE_PYTHON, True)

    ##########################################################################################################################################################

    # [2] h5 version #
    dataObj.OpenHDF5toWrite()
    dataObj.CreateHDF5Group()
    dataObj.ReadDataSequenceHDF5(USB_CDC_START_DATA, USB_CDC_END_DATA, USB_CDC_TERMINATE_PYTHON, True)

    ##########################################################################################################################################################

    # [3] h5 version with keyboard labeling #
    # dataObj.OpenHDF5toWrite()
    # dataObj.CreateHDF5Group()
    # dataObj.ReadDataSequenceHDF5_labeling(USB_CDC_START_DATA, USB_CDC_END_DATA, USB_CDC_TERMINATE_PYTHON, True)

    ##########################################################################################################################################################

if __name__ == '__main__':
    main()



# data = pd.read_csv(csv_filename, header=0)

# plt.figure(figsize=(14,8), dpi=120)
# plt.plot(data['Time[ms]'], data['EMG_Raw'], label='EMG_Raw', color='black')
# plt.plot(data['Time[ms]'], data['EMG_Processed'], label='EMG_Processed', color='r')
# plt.xlabel('Time[ms]', fontsize=15)
# plt.ylabel('% MVIC', fontsize=15)
# plt.ylim(-1, 1)
# plt.title('Result of UART TEST', fontsize=25)
# plt.grid(alpha=0.4)
# plt.legend(loc=1, fontsize=15)
# plt.savefig('UART_TEST_1NE.png')  
# plt.show()