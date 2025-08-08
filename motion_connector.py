from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty, pyqtSlot, QVariant, QThread, QWaitCondition, QMutex, QMutexLocker
from typing import List
import logging
import base58
import json
import csv
import os
import datetime
import time
import random
import string

from motion_singleton import motion_interface  

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or INFO depending on what you want to see

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
    logger.addHandler(ch)

# Define system states
DISCONNECTED = 0
SENSOR_CONNECTED  = 1
CONSOLE_CONNECTED = 2
READY = 3
RUNNING = 4

class MOTIONConnector(QObject):
    # Ensure signals are correctly defined
    signalConnected = pyqtSignal(str, str)  # (descriptor, port)
    signalDisconnected = pyqtSignal(str, str)  # (descriptor, port)
    signalDataReceived = pyqtSignal(str, str)  # (descriptor, data)

    connectionStatusChanged = pyqtSignal()  # 🔹 New signal for connection updates
    stateChanged = pyqtSignal()  # Signal to notify QML of state changes
    laserStateChanged = pyqtSignal()  # Signal to notify QML of laser state changes
    safetyFailureStateChanged = pyqtSignal()  # Signal to notify QML of safety
    triggerStateChanged = pyqtSignal()  # Signal to notify QML of trigger state changes
    directoryChanged = pyqtSignal()  # Signal to notify QML of directory changes
    subjectIdChanged = pyqtSignal()  # Signal to notify QML of subject ID changes
    sensorDeviceInfoReceived = pyqtSignal(str, str)  # (fw_version, device_id)
    consoleDeviceInfoReceived = pyqtSignal(str, str)  # (fw_version, device_id)
    temperatureSensorUpdated = pyqtSignal(float)  # Temperature data
    accelerometerSensorUpdated = pyqtSignal(float, float, float)  # (x, y, z)
    gyroscopeSensorUpdated = pyqtSignal(float, float, float)  # (x, y, z)
    rgbStateReceived = pyqtSignal(int, str)  # (state, state_text)


    def __init__(self):
        super().__init__()
        self._interface = motion_interface

        # Check if console and sensor are connected
        console_connected, left_sensor_connected, right_sensor_connected = motion_interface.is_device_connected()

        self._leftSensorConnected = left_sensor_connected
        self._rightSensorConnected = right_sensor_connected
        self._consoleConnected = console_connected
        self._laserOn = False
        self._safetyFailure = False
        self._running = False
        self._trigger_state = "OFF"
        self._state = DISCONNECTED

        self.connect_signals()

        default_dir = os.path.join(os.getcwd(), "scan_data")
        os.makedirs(default_dir, exist_ok=True)
        self._directory = default_dir
        logger.info(f"[Connector] Default directory initialized to: {self._directory}")

        self._subject_id = self.generate_subject_id()
        logger.info(f"[Connector] Generated subject ID: {self._subject_id}")

    def _refresh_connections(self):
        """Re-read connection states from motion_interface and notify QML."""
        console_connected, left_sensor_connected, right_sensor_connected = self._interface.is_device_connected()
        logger.info(f"Connection status updated: Console={console_connected}, Left Sensor={left_sensor_connected}, Right Sensor={right_sensor_connected}")
        changed = (
            self._consoleConnected != console_connected or
            self._leftSensorConnected != left_sensor_connected or
            self._rightSensorConnected != right_sensor_connected
        )

        self._consoleConnected = console_connected
        self._leftSensorConnected = left_sensor_connected
        self._rightSensorConnected = right_sensor_connected

        if changed:
            self.connectionStatusChanged.emit()
        self.update_state()
        
    def connect_signals(self):
        """Connect LIFUInterface signals to QML."""
        motion_interface.signal_connect.connect(self.on_connected)
        motion_interface.signal_disconnect.connect(self.on_disconnected)
        motion_interface.signal_data_received.connect(self.on_data_received)

    def generate_subject_id(self):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ow{suffix}"
    
    def update_state(self):
        """Update system state based on connection and configuration."""
        if not self._consoleConnected and ((not self._leftSensorConnected) or (not self._rightSensorConnected)):
            self._state = DISCONNECTED
        elif self._leftSensorConnected and not self._consoleConnected:
            self._state = SENSOR_CONNECTED
        elif self._consoleConnected and not self._leftSensorConnected:
            self._state = CONSOLE_CONNECTED
        elif self._consoleConnected and self._leftSensorConnected:
            self._state = READY
        elif self._consoleConnected and self._leftSensorConnected and self._running:
            self._state = RUNNING
        self.stateChanged.emit()  # Notify QML of state update
        logger.info(f"Updated state: {self._state}")
        
    @property
    def interface(self):
        return motion_interface
    
    # --- getters/setters for Qt ---
    def getSubjectId(self) -> str:
        return self._subject_id

    def setSubjectId(self, value: str):
        if not value:
            return
        # normalize to "ow" + alphanumerics (uppercase)
        if value.startswith("ow"):
            rest = value[2:]
        else:
            rest = value
        rest = "".join(ch for ch in rest.upper() if ch.isalnum())
        new_val = "ow" + rest
        if new_val != self._subject_id:
            self._subject_id = new_val
            self.subjectIdChanged.emit()

    subjectId = pyqtProperty(str, fget=getSubjectId, fset=setSubjectId, notify=subjectIdChanged)
    
    @pyqtProperty(bool, notify=connectionStatusChanged)
    def leftSensorConnected(self):
        """Expose Sensor connection status to QML."""
        return self._leftSensorConnected

    @pyqtProperty(bool, notify=connectionStatusChanged)
    def rightSensorConnected(self):
        """Expose Sensor connection status to QML."""
        return self._rightSensorConnected
    
    @pyqtProperty(bool, notify=connectionStatusChanged)
    def consoleConnected(self):
        """Expose Console connection status to QML."""
        return self._consoleConnected

    @pyqtProperty(bool, notify=laserStateChanged)
    def laserOn(self):
        """Expose Console connection status to QML."""
        return self._laserOn
    
    @pyqtProperty(bool, notify=safetyFailureStateChanged)
    def safetyFailure(self):
        """Expose Console connection status to QML."""
        return self._safetyFailure

    @pyqtProperty(int, notify=stateChanged)
    def state(self):
        """Expose state as a QML property."""
        return self._state
    
    @pyqtProperty(str, notify=triggerStateChanged)
    def triggerState(self):
        return self._trigger_state

    @pyqtProperty(str, notify=directoryChanged)
    def directory(self):
        return self._directory

    @directory.setter
    def directory(self, path):
        # Normalize incoming QML "file:///" path
        if path.startswith("file:///"):
            path = path[8:] if path[9] != ':' else path[8:]
        self._directory = path
        print(f"[Connector] Default directory set to: {self._directory}")
        self.directoryChanged.emit()
    
    @pyqtSlot(result=str)
    def get_sdk_version(self):
        return self._interface.get_sdk_version()
    
    @pyqtSlot(str, str)
    def on_connected(self, descriptor, port):
        """Handle device connection."""
        print(f"Device connected: {descriptor} on port {port}")
        if descriptor.upper() == "SENSOR_LEFT":
            self._leftSensorConnected = True
        if descriptor.upper() == "SENSOR_RIGHT":
            self._rightSensorConnected = True
        elif descriptor.upper() == "CONSOLE":
            self._consoleConnected = True

        self.signalConnected.emit(descriptor, port)
        self.connectionStatusChanged.emit() 
        self.update_state()

    @pyqtSlot(str, str)
    def on_disconnected(self, descriptor, port):
        """Handle device disconnection."""
        if descriptor.upper() == "SENSOR_LEFT":
            self._leftSensorConnected = False
        elif descriptor.upper() == "SENSOR_RIGHT":
            self._rightSensorConnected = False
        elif descriptor.upper() == "CONSOLE":
            self._consoleConnected = False

        print(f"Device disconnected: {descriptor} on port {port}")
        self.signalDisconnected.emit(descriptor, port)
        self.connectionStatusChanged.emit() 
        self.update_state()
    
    @pyqtSlot()
    def refreshConnections(self):
        self._refresh_connections()

    @pyqtSlot(str, str)
    def on_data_received(self, descriptor, message):
        """Handle incoming data from the LIFU device."""
        logger.info(f"Data received from {descriptor}: {message}")
        self.signalDataReceived.emit(descriptor, message)

    @pyqtSlot(str)
    def querySensorInfo(self, target: str):
        """Fetch and emit device information."""
        try:
            if target == "SENSOR_LEFT" or target == "SENSOR_RIGHT":                
                sensor_tag = "left" if target == "SENSOR_LEFT" else "right"
            else:
                logger.error(f"Invalid target for sensor info query: {target}")
                return
            fw_version = motion_interface.sensors[sensor_tag].get_version()
            logger.info(f"Version: {fw_version}")
            hw_id = motion_interface.sensors[sensor_tag].get_hardware_id()
            device_id = base58.b58encode(bytes.fromhex(hw_id)).decode()
            self.sensorDeviceInfoReceived.emit(fw_version, device_id)
            logger.info(f"Sensor Device Info - Firmware: {fw_version}, Device ID: {device_id}")
        except Exception as e:
            logger.error(f"Error querying device info: {e}")

    @pyqtSlot()
    def queryConsoleInfo(self):
        """Fetch and emit device information."""
        try:
            fw_version = motion_interface.console_module.get_version()
            logger.info(f"Version: {fw_version}")
            hw_id = motion_interface.console_module.get_hardware_id()
            device_id = base58.b58encode(bytes.fromhex(hw_id)).decode()
            self.consoleDeviceInfoReceived.emit(fw_version, device_id)
            logger.info(f"Console Device Info - Firmware: {fw_version}, Device ID: {device_id}")
        except Exception as e:
            logger.error(f"Error querying device info: {e}")

    @pyqtSlot(str)
    def querySensorTemperature(self, target: str):
        """Fetch and emit Temperature data."""
        try:
            if target == "SENSOR_LEFT" or target == "SENSOR_RIGHT":                
                sensor_tag = "left" if target == "SENSOR_LEFT" else "right"
            else:
                logger.error(f"Invalid target for sensor info query: {target}")
                return
            imu_temp = motion_interface.sensors[sensor_tag].imu_get_temperature()  
            logger.info(f"Temperature Data - IMU Temp: {imu_temp}")
            self.temperatureSensorUpdated.emit(imu_temp)
        except Exception as e:
            logger.error(f"Error querying Temperature data: {e}")

    @pyqtSlot(int)
    def setRGBState(self, state):
        """Set the RGB state using integer values."""
        try:
            valid_states = [0, 1, 2, 3]
            if state not in valid_states:
                logger.error(f"Invalid RGB state value: {state}")
                return

            if motion_interface.console_module.set_rgb_led(state) == state:
                logger.info(f"RGB state set to: {state}")
            else:
                logger.error(f"Failed to set RGB state to: {state}")
        except Exception as e:
            logger.error(f"Error setting RGB state: {e}")

    @pyqtSlot()
    def queryRGBState(self):
        """Fetch and emit RGB state."""
        try:
            state = motion_interface.console_module.get_rgb_led()
            state_text = {0: "Off", 1: "IND1", 2: "IND2", 3: "IND3"}.get(state, "Unknown")

            logger.info(f"RGB State: {state_text}")
            self.rgbStateReceived.emit(state, state_text)  # Emit both values
        except Exception as e:
            logger.error(f"Error querying RGB state: {e}")

    @pyqtSlot(result=QVariant)
    def queryTriggerConfig(self):
        trigger_setting = motion_interface.console_module.get_trigger_json()
        if trigger_setting:
            if isinstance(trigger_setting, str):
                updateTrigger = json.loads(trigger_setting)
            else:
                updateTrigger = trigger_setting
            if updateTrigger["TriggerStatus"] == 2:               
                self._trigger_state = "ON"
                self.triggerStateChanged.emit("ON")            
                return trigger_setting or {}
       
        self._trigger_state = "OFF"
        self.triggerStateChanged.emit("OFF")
                
        return trigger_setting or {}
    
    @pyqtSlot(str, result=bool)
    def setTrigger(self, triggerjson):
        try:
            json_trigger_data = json.loads(triggerjson)
            
            trigger_setting = motion_interface.console_module.set_trigger_json(data=json_trigger_data)
            if trigger_setting:
                logger.info(f"Trigger Setting: {trigger_setting}")
                return True
            else:
                logger.error("Failed to set trigger setting.")
                return False

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON data: {e}")
            return False

        except AttributeError as e:
            logger.error(f"Invalid interface or method: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error while setting trigger: {e}")
            return False
            
    @pyqtSlot(result=bool)
    def startTrigger(self):
        success = motion_interface.console_module.start_trigger()
        if success:

            # Start status thread
            if self._console_status_thread is None:
                self._console_status_thread = ConsoleStatusThread(self)
                self._console_status_thread.statusUpdate.connect(self.handleUpdateCapStatus)  # Or define a dedicated signal
                self._console_status_thread.start()

            self._trigger_state = "ON"
            self.triggerStateChanged.emit("ON")
        return success
        
    @pyqtSlot()
    def stopTrigger(self):
        motion_interface.console_module.stop_trigger()
        self._trigger_state = "OFF"
        self.triggerStateChanged.emit("OFF")        
        
        if self._console_status_thread:
            self._console_status_thread.stop()
            self._console_status_thread = None
    
    
    @pyqtSlot(str)
    def querySensorAccelerometer (self, target: str):
        """Fetch and emit Accelerometer data."""
        try:
            if target == "SENSOR_LEFT" or target == "SENSOR_RIGHT":                
                sensor_tag = "left" if target == "SENSOR_LEFT" else "right"
            else:
                logger.error(f"Invalid target for sensor info query: {target}")
                return
            accel = motion_interface.sensors[sensor_tag].imu_get_accelerometer()
            logger.info(f"Accel (raw): X={accel[0]}, Y={accel[1]}, Z={accel[2]}")
            self.accelerometerSensorUpdated.emit(accel[0], accel[1], accel[2])
        except Exception as e:
            logger.error(f"Error querying Accelerometer data: {e}")

    @pyqtSlot()
    def querySensorGyroscope (self):
        """Fetch and emit Gyroscope data."""
        try:
            gyro  = motion_interface.sensors["left"].imu_get_gyroscope()
            logger.info(f"Gyro  (raw): X={gyro[0]}, Y={gyro[1]}, Z={gyro[2]}")
            self.gyroscopeSensorUpdated.emit(gyro[0], gyro[1], gyro[2])
        except Exception as e:
            logger.error(f"Error querying Gyroscope data: {e}")

    @pyqtSlot(str)
    def softResetSensor(self, target: str):
        """reset hardware Sensor device."""
        try:
            
            if target == "CONSOLE":
                if motion_interface.console_module.soft_reset():
                    logger.info(f"Software Reset Sent")
                else:
                    logger.error(f"Failed to send Software Reset")
            elif target == "SENSOR_LEFT" or target == "SENSOR_RIGHT":
                sensor_tag = "left" if target == "SENSOR_LEFT" else "right"                    
                if motion_interface.sensors[sensor_tag].soft_reset():
                    logger.info(f"Software Reset Sent")
                else:
                    logger.error(f"Failed to send Software Reset")
        except Exception as e:
            logger.error(f"Error Sending Software Reset: {e}")
    
    @pyqtSlot()
    def readSafetyStatus(self):
        # Replace this with your actual console status check
        try:
            muxIdx = 1
            i2cAddr = 0x41
            offset = 0x24  
            data_len = 1  # Number of bytes to read

            channels = {
                "SE": 6,
                "SO": 7
            }
            statuses = {}

            for label, channel in channels.items():
                status = self.i2cReadBytes("CONSOLE", muxIdx, channel, i2cAddr, offset, data_len)
                if status:
                    statuses[label] = status[0]                
                else:
                    raise Exception("I2C read error")
                
            status_text = f"SE: 0x{statuses['SE']:02X}, SO: 0x{statuses['SO']:02X}"
            
            if (statuses["SE"] & 0x0F) == 0 and (statuses["SO"] & 0x0F) == 0:
                if self._safetyFailure:
                    self._safetyFailure = False
                    self.safetyFailureStateChanged.emit(False)
            else:
                if not self._safetyFailure:
                    self._safetyFailure = True
                    self.stopTrigger()
                    self.laserStateChanged.emit(False)
                    self.safetyFailureStateChanged.emit(True)  
                    logging.error(f"Failure Detected: {status_text}")

            # Emit combined status if needed
            
            logging.info(f"Status QUERY: {status_text}")

        except Exception as e:
            logging.error(f"Console status query failed: {e}")
                
    @pyqtSlot()
    def shutdown(self):
        logger.info("Shutting down MOTIONConnector...")

        if self._capture_thread:
            self._capture_thread.stop()
            self._capture_thread = None
        
        if self._console_status_thread:
            self._console_status_thread.stop()
            self._console_status_thread = None

                