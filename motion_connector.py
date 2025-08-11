from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty, pyqtSlot, QVariant, QThread, QWaitCondition, QMutex, QMutexLocker
from typing import List
from pathlib import Path
import logging
import base58
import threading
import queue
import json
import csv
import os
import datetime
import time
import random
import re
import string

from motion_singleton import motion_interface  
from processing.data_processing import DataProcessor 
from utils.resource_path import resource_path

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
    errorOccurred = pyqtSignal(str)
    vizFinished = pyqtSignal()
    visualizingChanged = pyqtSignal(bool)  

    configProgress = pyqtSignal(int)
    configLog = pyqtSignal(str)
    configFinished = pyqtSignal(bool, str)

    # capture signals
    captureProgress = pyqtSignal(int)                       # 0..100
    captureLog = pyqtSignal(str)                            # log lines
    captureFinished = pyqtSignal(bool, str, str, str)       # ok, error, leftPath, rightPath
    scanNotesChanged = pyqtSignal()

    # post-processing signals
    postProgress = pyqtSignal(int)
    postLog = pyqtSignal(str)
    postFinished = pyqtSignal(bool, str, str, str)  # ok, err, leftCsv, rightCsv

    def __init__(self, config_dir="config", parent=None):
        super().__init__(parent)
        self._interface = motion_interface

        # Check if console and sensor are connected
        console_connected, left_sensor_connected, right_sensor_connected = motion_interface.is_device_connected()

        self._leftSensorConnected = left_sensor_connected
        self._rightSensorConnected = right_sensor_connected
        self._consoleConnected = console_connected
        self._config_thread = None
        self._laserOn = False
        self._safetyFailure = False
        self._running = False
        self._trigger_state = "OFF"
        self._state = DISCONNECTED
        self.laser_params = self._load_laser_params(config_dir)

        self._post_thread = None
        self._post_cancel = threading.Event()

        self._capture_thread = None
        self._capture_stop = threading.Event()
        self._capture_running = False
        self._capture_left_path = ""
        self._capture_right_path = ""
        self._scan_notes = ""  
        self.connect_signals()
        self._viz_thread = None
        self._viz_worker = None


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

    def _load_laser_params(self, config_dir):
        
        config_path = resource_path("config", "laser_params.json") if config_dir == "config" else Path(config_dir) / "laser_params.json"
        if not config_path.exists():
            logger.error(f"[Connector] Laser parameter file not found: {config_path}")
            return []  
        
        try:
            with open(config_path, "r") as f:
                params = json.load(f)
            logger.info(f"[Connector] Loaded {len(params)} laser parameter sets from {config_path}")
            return params
        except FileNotFoundError:
            logger.error(f"[Connector] Laser parameter file not found: {config_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"[Connector] Invalid JSON in {config_path}: {e}")
            return []
        
    def _write_stream_to_file(self, q: queue.Queue, stop_evt: threading.Event, filename: str):
        try:
            with open(filename, "wb") as f:
                while not stop_evt.is_set() or not q.empty():
                    try:
                        data = q.get(timeout=0.100)
                        if data:
                            f.write(data)
                        q.task_done()
                    except queue.Empty:
                        continue
        except Exception as e:
            self.captureLog.emit(f"Writer error ({filename}): {e}")
            
    def set_laser_power_from_config(self, interface):
        logger.info("[Connector] Setting laser power from config...")
        for idx, laser_param in enumerate(self.laser_params, start=1):
            muxIdx = laser_param["muxIdx"]
            channel = laser_param["channel"]
            i2cAddr = laser_param["i2cAddr"]
            offset = laser_param["offset"]
            dataToSend = bytearray(laser_param["dataToSend"])

            logger.debug(
                f"[Connector] ({idx}/{len(self.laser_params)}) "
                f"Writing I2C: muxIdx={muxIdx}, channel={channel}, "
                f"i2cAddr=0x{i2cAddr:02X}, offset=0x{offset:02X}, "
                f"data={list(dataToSend)}"
            )

            if not interface.console_module.write_i2c_packet(
                mux_index=muxIdx, channel=channel,
                device_addr=i2cAddr, reg_addr=offset,
                data=dataToSend
            ):
                logger.error(f"Failed to set laser power (muxIdx={muxIdx}, channel={channel})")
                return False
        logger.info("Laser power set successfully.")
        return True
        
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

    @pyqtProperty(str, notify=scanNotesChanged)   # <-- add notify
    def scanNotes(self):
         return self._scan_notes

    @scanNotes.setter
    def scanNotes(self, value: str):
        value = value or ""
        if value != self._scan_notes:
            self._scan_notes = value
            self.scanNotesChanged.emit()  
            
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

    @pyqtSlot(result=bool)
    def setLaserPowerFromConfig(self) -> bool:
        """Apply laser power parameters loaded at startup."""
        try:
            return self.set_laser_power_from_config(self._interface)
        except Exception as e:
            logger.error(f"setLaserPowerFromConfig error: {e}")
            return False
        
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
                self.triggerStateChanged.emit()            
                return trigger_setting or {}
       
        self._trigger_state = "OFF"
        self.triggerStateChanged.emit()
                
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
            self._trigger_state = "ON"
            self.triggerStateChanged.emit()
            logger.info("Trigger started successfully.")
        return success
        
    @pyqtSlot()
    def stopTrigger(self):
        motion_interface.console_module.stop_trigger()
        self._trigger_state = "OFF"
        self.triggerStateChanged.emit()        
        logger.info("Trigger stopped.")   
    
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

    @pyqtSlot(str, str, result=bool)
    def startPostProcess(self, left_raw: str, right_raw: str) -> bool:
        """
        Convert left/right .raw to .csv in-place (same directory).
        Returns False if a post job is already running.
        """
        if self._post_thread is not None:
            self.postLog.emit("Post-process already running.")
            return False

        left_raw = left_raw or ""
        right_raw = right_raw or ""
        self._post_cancel = threading.Event()

        def _worker():
            ok = True
            err = ""
            left_csv = ""
            right_csv = ""

            try:
                proc = DataProcessor()

                def _to_csv_path(p):
                    base, ext = os.path.splitext(p)
                    return base + ".csv" if base else ""

                # Process LEFT
                if left_raw and os.path.isfile(left_raw):
                    self.postLog.emit(f"Processing LEFT: {os.path.basename(left_raw)}")
                    self.postProgress.emit(5)
                    left_csv = _to_csv_path(left_raw)
                    proc.process_bin_file(left_raw, left_csv)
                    self.postLog.emit(f"LEFT → {os.path.basename(left_csv)}")
                    self.postProgress.emit(50)
                else:
                    if left_raw:
                        self.postLog.emit(f"LEFT missing: {left_raw}")
                    self.postProgress.emit(50)

                # Cancel check between files
                if self._post_cancel.is_set():
                    ok = False
                    err = "Canceled"
                    return

                # Process RIGHT
                if right_raw and os.path.isfile(right_raw):
                    self.postLog.emit(f"Processing RIGHT: {os.path.basename(right_raw)}")
                    self.postProgress.emit(55)
                    right_csv = _to_csv_path(right_raw)
                    proc.process_bin_file(right_raw, right_csv)
                    self.postLog.emit(f"RIGHT → {os.path.basename(right_csv)}")
                    self.postProgress.emit(95)
                else:
                    if right_raw:
                        self.postLog.emit(f"RIGHT missing: {right_raw}")
                    self.postProgress.emit(95)

                self.postProgress.emit(100)

            except Exception as e:
                ok = False
                err = str(e)
                self.postLog.emit(f"Post-process error: {err}")
            finally:
                # clear thread handle before emitting
                self._post_thread = None
                self.postFinished.emit(ok, err, left_csv or "", right_csv or "")
                logger.info(f"Post-process finished: ok={ok}, err={err}, left_csv={left_csv}, right_csv={right_csv}")

        self._post_thread = threading.Thread(target=_worker, daemon=True)
        self._post_thread.start()
        return True

    @pyqtSlot()
    def cancelPostProcess(self):
        """Request cancel; takes effect between files."""
        if self._post_thread is None:
            return
        self.postLog.emit("Cancel requested.")
        self._post_cancel.set()
    
    @pyqtSlot(int)
    def startConfigureCameraSensors(self, camera_mask:int):
        if self._config_thread: return
        w = _ConfigureWorker(self._interface, camera_mask)
        w.progress.connect(self.configProgress.emit)
        w.log.connect(self.configLog.emit)
        w.finished.connect(self._on_config_finished)
        self._config_thread = w
        w.start()

    @pyqtSlot()
    def cancelConfigureCameraSensors(self):
        if self._config_thread: self._config_thread.stop()

    def _on_config_finished(self, ok:bool, err:str):
        if self._config_thread:
            self._config_thread.quit(); self._config_thread.wait(2000); self._config_thread = None
        self.configFinished.emit(ok, err)

    @pyqtSlot(int, result=bool)
    def configureCameraSensors(self, camera_mask: int) -> bool:
        """
        Programs the FPGA on each selected camera and configures sensor registers.
        camera_mask: bitmask over 8 camera positions (bit 0 => position 1, etc.)
        Returns True on full success, False if any step fails.
        """
        logger.info(f"[Connector] configureCameraSensors called with mask=0x{camera_mask:02X}")
        try:
            start_time = time.time()
            interface = self._interface  # motion_interface singleton

            # Turn mask into positions [0..7] (bits set)
            camera_positions = [i for i in range(8) if (camera_mask & (1 << i))]
            if not camera_positions:
                logger.error("configureCameraSensors: camera_mask is empty (0).")
                return False

            for pos in camera_positions:
                cam_mask_single = 1 << pos
                logger.info(f"Programming camera FPGA at position {pos + 1} (mask 0x{cam_mask_single:02X})…")

                # 1) Program FPGA
                results = interface.run_on_sensors(
                    "program_fpga",
                    camera_position=cam_mask_single,
                    manual_process=False
                )
                # Expecting a dict like {"left": True/False, "right": True/False}
                if isinstance(results, dict):
                    for side, success in results.items():
                        if not success:
                            logger.error(f"Failed to program FPGA on {side} sensor (pos {pos+1}).")
                            return False
                elif results is not True:
                    logger.error(f"program_fpga returned unexpected result: {results!r}")
                    return False

                # 2) Configure camera sensor registers
                logger.info(f"Configuring camera sensor registers at position {pos + 1}…")
                cfg_res = interface.run_on_sensors(
                    "camera_configure_registers",
                    camera_position=cam_mask_single
                )
                # Many backends return dict/bool; treat Falsey as failure
                if not cfg_res:
                    logger.error(f"camera_configure_registers failed at position {pos + 1}: {cfg_res!r}")
                    return False

            elapsed_ms = (time.time() - start_time) * 1000.0
            logger.info(f"FPGAs programmed & registers configured | Time: {elapsed_ms:.2f} ms")
            return True

        except Exception as e:
            logger.exception(f"configureCameraSensors error: {e}")
            return False

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

    @pyqtSlot(result=list)
    def get_scan_list(self):
        """Return sorted list of scans like 'owABCD12_YYYYMMDD_HHMMSS'."""
        base_path = Path(self._directory)
        if not base_path.exists():
            return []

        ids = []
        for f in base_path.glob("scan_*_notes.txt"):
            if not f.is_file():
                continue
            stem = f.stem  # e.g., "scan_owIZGDFP_20250808_120740_notes"
            # strip leading "scan_" and trailing "_notes"
            if stem.startswith("scan_"):
                stem = stem[5:]
            if stem.endswith("_notes"):
                stem = stem[:-6]
            ids.append(stem)

        # sort by timestamp desc; assumes format owXXXXXX_YYYYMMDD_HHMMSS
        def ts_key(s):
            parts = s.split("_", 1)
            return parts[1] if len(parts) == 2 else s
        return sorted(ids, key=ts_key, reverse=True)

    @pyqtSlot(str, result=QVariant)
    def get_scan_details(self, scan_id: str):
        """
        scan_id like 'owIZGDFP_20250808_120740' (no 'scan_' prefix).
        """
        base = Path(self._directory)
        try:
            subject, ts = scan_id.split("_", 1)
        except ValueError:
            return {}

        notes_path = base / f"scan_{scan_id}_notes.txt"
        left  = next(base.glob(f"scan_{scan_id}_left_mask*.raw"), None)
        right = next(base.glob(f"scan_{scan_id}_right_mask*.raw"), None)

        mask = ""
        for p in (left, right):
            if p:
                m = re.search(r"_mask([0-9A-Fa-f]+)\.raw$", p.name)
                if m:
                    mask = m.group(1)
                    break

        notes = ""
        try:
            notes = notes_path.read_text(encoding="utf-8")
        except Exception:
            pass

        return {
            "subjectId": subject,
            "timestamp": ts,
            "maskHex": mask,
            "leftPath": str(left) if left else "",
            "rightPath": str(right) if right else "",
            "notesPath": str(notes_path),
            "notes": notes,
        }


    @pyqtSlot()
    def shutdown(self):
        logger.info("Shutting down MOTIONConnector...")

        if self._capture_thread:
            self._capture_thread.stop()
            self._capture_thread = None
        
        if self._console_status_thread:
            self._console_status_thread.stop()
            self._console_status_thread = None

    @pyqtSlot(str, int, int, str, bool, result=bool)
    def startCapture(self, subject_id: str, duration_sec: int, camera_mask: int, data_dir: str, disable_laser: bool) -> bool:
        """Start capture asynchronously; returns True if kicked off."""
        logger.info(
            f"startCapture(subject_id={subject_id}, dur={duration_sec}s, mask=0x{camera_mask:02X}, dir={data_dir}, disable_laser={disable_laser})"
        )

        if self._capture_running or self._capture_thread is not None:
            self.captureLog.emit("Capture already running.")
            return False

        # sanitize/prepare
        try:
            os.makedirs(data_dir, exist_ok=True)
        except Exception as e:
            self.captureLog.emit(f"Failed to create data dir: {e}")
            return False

        logger.info("Capture worker thread starting…")
        self._capture_stop = threading.Event()
        self._capture_running = True
        self._capture_left_path = ""
        self._capture_right_path = ""

        def _worker():
            ok = False
            err = ""
            left_path = ""
            right_path = ""

            try:
                interface = self._interface
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self.captureLog.emit("Preparing capture…")

                # Frame sync choice
                if not disable_laser:
                    self.captureLog.emit("Enabling external frame sync…")
                    results = interface.run_on_sensors("enable_camera_fsin_ext")
                    if isinstance(results, dict):
                        for side, success in results.items():
                            if not success:
                                err = f"Failed to enable external frame sync on {side}."
                                self.captureLog.emit(err); raise RuntimeError(err)
                    else:
                        self.captureLog.emit("enable_camera_fsin_ext returned unexpected result")

                # Enable cameras
                self.captureLog.emit("Enabling cameras…")
                results = interface.run_on_sensors("enable_camera", camera_mask)
                if isinstance(results, dict):
                    for side, success in results.items():
                        if not success:
                            err = f"Failed to enable camera on {side}."
                            self.captureLog.emit(err); raise RuntimeError(err)

                # Setup streaming per connected sensor
                qmap = {}
                writer_threads = {}
                writer_stops = {}
                expected_size = 32833  # TODO: adjust if mask implies different payload size

                for side in ("left", "right"):
                    sensor = interface.sensors.get(side)
                    if sensor and sensor.is_connected():
                        q = queue.Queue()
                        stop_evt = threading.Event()
                        # start device streaming into queue
                        sensor.uart.histo.start_streaming(q, expected_size=expected_size)

                        filename = f"scan_{subject_id}_{ts}_{side}_mask{camera_mask:02X}.raw"
                        filepath = os.path.join(data_dir, filename)
                        t = threading.Thread(target=self._write_stream_to_file, args=(q, stop_evt, filepath), daemon=True)
                        t.start()

                        qmap[side] = q
                        writer_threads[side] = t
                        writer_stops[side] = stop_evt
                        if side == "left": left_path = filepath
                        if side == "right": right_path = filepath
                        self.captureLog.emit(f"[{side.upper()}] Streaming to: {filename}")

                self._capture_left_path = left_path
                self._capture_right_path = right_path

                # Start trigger
                self.captureLog.emit("Starting trigger…")
                if not interface.console_module.start_trigger():
                    err = "Failed to start trigger."
                    self.captureLog.emit(err); raise RuntimeError(err)
                self._trigger_state = "ON"; self.triggerStateChanged.emit()

                # Progress loop
                start_t = time.time()
                last_emit = -1
                while not self._capture_stop.is_set():
                    elapsed = time.time() - start_t
                    pct = int(min(100, max(0, (elapsed / max(1, duration_sec)) * 100)))
                    if pct != last_emit:
                        self.captureProgress.emit(pct if pct >= 1 else 1)
                        last_emit = pct
                    if elapsed >= duration_sec:
                        break
                    time.sleep(0.2)

                # Stop trigger
                self.captureLog.emit("Stopping trigger…")
                try:
                    interface.console_module.stop_trigger()
                finally:
                    self._trigger_state = "OFF"; self.triggerStateChanged.emit()

                # Disable cameras
                self.captureLog.emit("Disabling cameras…")
                results = interface.run_on_sensors("disable_camera", camera_mask)
                if isinstance(results, dict):
                    for side, success in results.items():
                        if not success:
                            self.captureLog.emit(f"Failed to disable camera on {side}.")

                # Stop sensor streaming
                for side in ("left", "right"):
                    sensor = interface.sensors.get(side)
                    if sensor:
                        try:
                            sensor.uart.histo.stop_streaming()
                        except Exception as e:
                            self.captureLog.emit(f"stop_streaming[{side}] error: {e}")

                # Stop writer threads
                for side, stop_evt in writer_stops.items():
                    stop_evt.set()
                for side, t in writer_threads.items():
                    t.join(timeout=5.0)

                ok = not self._capture_stop.is_set()
                if ok:
                    self.captureLog.emit("Capture session complete.")
                    # save notes file for the whole scan
                    try:
                        notes_filename = f"scan_{subject_id}_{ts}_notes.txt"
                        notes_path = os.path.join(data_dir, notes_filename)
                        with open(notes_path, "w", encoding="utf-8") as nf:
                            nf.write(self._scan_notes.strip() + "\n")
                        logger.info(f"Saved scan notes to {notes_path}")
                    except Exception as e:
                        logger.error(f"Failed to save scan notes: {e}")
                else:
                    err = "Capture canceled"

            except Exception as e:
                err = str(e)
                self.captureLog.emit(f"Capture error: {err}")
                ok = False
            finally:
                self._capture_running = False
                self._capture_thread = None
                self.captureFinished.emit(ok, err, left_path, right_path)

        # launch worker
        self._capture_thread = threading.Thread(target=_worker, daemon=True)
        self._capture_thread.start()
        return True

    @pyqtSlot()
    def stopCapture(self):
        """Request capture cancellation."""
        if not self._capture_running:
            return
        self.captureLog.emit("Cancel requested.")
        self._capture_stop.set()
        # also stop trigger ASAP
        try:
            self._interface.console_module.stop_trigger()
            self._trigger_state = "OFF"; self.triggerStateChanged.emit()
        except Exception:
            pass

    @pyqtSlot(str, str, float, float, result=bool)
    def visualize_bloodflow(self, left_csv: str, right_csv: str, t1: float = 0.0, t2: float = 120.0) -> bool:
        left_csv  = (left_csv or "").strip()
        right_csv = (right_csv or "").strip()
        if left_csv.lower().endswith(".raw"):  left_csv  = left_csv[:-4]  + ".csv"
        if right_csv.lower().endswith(".raw"): right_csv = right_csv[:-4] + ".csv"

        if not left_csv and not right_csv:
            self.errorOccurred.emit("No files selected. Please pick a left and/or right CSV.")
            return False

        missing = []
        if left_csv and not Path(left_csv).exists():   missing.append(f"Left file not found:\n{left_csv}")
        if right_csv and not Path(right_csv).exists(): missing.append(f"Right file not found:\n{right_csv}")
        if missing:
            self.errorOccurred.emit("\n\n".join(missing))
            return False

        logger.info(f"Visualizing bloodflow: left_csv={left_csv}, right_csv={right_csv}, t1={t1}, t2={t2}")

        # start spinner
        self.visualizingChanged.emit(True)

        # start worker thread (compute only)
        self._viz_thread = QThread(self)
        self._viz_worker = _VizWorker(left_csv, right_csv, t1, t2)
        self._viz_worker.moveToThread(self._viz_thread)

        # --- connections when starting the worker ---
        self._viz_thread.started.connect(self._viz_worker.run)
        self._viz_worker.resultsReady.connect(self._onVizResults)  # will pass 1 arg
        self._viz_worker.error.connect(self._onVizError)
        self._viz_worker.finished.connect(self._viz_thread.quit)
        self._viz_worker.finished.connect(self._viz_worker.deleteLater)
        self._viz_thread.finished.connect(self._viz_thread.deleteLater)
        self._viz_thread.start()
        return True

    @pyqtSlot(object)
    def _onVizResults(self, payload: dict):
        try:
            import matplotlib.pyplot as plt
            from processing.visualize_bloodflow import VisualizeBloodflow

            bfi = payload["bfi"]; bvi = payload["bvi"]
            camera_inds = payload["camera_inds"]
            nmodules = payload["nmodules"]
            t1 = payload["t1"]; t2 = payload["t2"]

            viz = VisualizeBloodflow(left_csv="", right_csv="", t1=t1, t2=t2)
            viz._BFI = bfi
            viz._BVI = bvi
            viz._camera_inds = camera_inds
            viz._nmodules = nmodules

            fig = viz.plot(("BFI", "BVI"))
            plt.show(block=False)
        except Exception as e:
            self.errorOccurred.emit(f"Visualization display failed:\n{e}")
        finally:
            self.visualizingChanged.emit(False)
            self.vizFinished.emit()

    @pyqtSlot(str)
    def _onVizError(self, msg: str):
        self.visualizingChanged.emit(False)
        self.errorOccurred.emit(f"Visualization failed:\n{msg}")

    @pyqtSlot()
    def _onVizFinished(self):
        # Show the figure on the main thread
        try:
            import matplotlib.pyplot as plt
            plt.show(block=False)
        except Exception as e:
            self.errorOccurred.emit(f"Visualization display failed:\n{e}")
        finally:
            self.visualizingChanged.emit(False)
            self.vizFinished.emit()

    @pyqtSlot(str)
    def emitError(self, msg):
        self.errorOccurred.emit(msg)

# --- worker to run visualiztion ---
class _VizWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    resultsReady = pyqtSignal(object)   # emits a dict with arrays/metadata

    def __init__(self, left_csv, right_csv, t1, t2):
        super().__init__()
        self.left_csv = left_csv
        self.right_csv = right_csv
        self.t1 = t1
        self.t2 = t2

    @pyqtSlot()
    def run(self):
        try:
            from processing.visualize_bloodflow import VisualizeBloodflow
            viz = VisualizeBloodflow(self.left_csv or None, self.right_csv or None, t1=self.t1, t2=self.t2)
            viz.compute()       

            # Save results CSV based on left_csv naming rule            
            new_file_name = re.sub(r"_left_mask\d+\.csv$", "_bfi_results.csv", self.left_csv)
            viz.save_results_csv(new_file_name)

            bfi, bvi, cam_inds = viz.get_results()
            payload = {"bfi": bfi, "bvi": bvi, "camera_inds": cam_inds,
                       "nmodules": 2 if self.right_csv else 1,
                       "freq": viz.frequency_hz, "t1": viz.t1, "t2": viz.t2}
            self.resultsReady.emit(payload)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

# --- worker to run config off the GUI thread ---
class _ConfigureWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    def __init__(self, interface, camera_mask:int):
        super().__init__()
        self.interface = interface
        self.camera_mask = camera_mask
        self._stop = False
    def stop(self): self._stop = True
    def run(self):
        import time
        # log hex mask
        logger.info(f"[Connector] configure worker mask=0x{self.camera_mask:02X}")
        positions = [i for i in range(8) if (self.camera_mask & (1<<i))]
        if not positions:
            self.finished.emit(False, "Empty camera mask"); return
        total= len(positions)*2; done=0
        for pos in positions:
            if self._stop: self.finished.emit(False,"Canceled"); return
            cam_mask_single = 1<<pos
            msg = f"Programming camera FPGA at position {pos+1} (mask 0x{cam_mask_single:02X})…"
            logger.info(msg); self.log.emit(msg)
            results = self.interface.run_on_sensors("program_fpga", camera_position=cam_mask_single, manual_process=False)
            if isinstance(results, dict):
                for side, ok in results.items():
                    if not ok:
                        err=f"Failed to program FPGA on {side} sensor (pos {pos+1})."
                        logger.error(err); self.log.emit(err); self.finished.emit(False, err); return
            elif results is not True:
                err=f"program_fpga unexpected: {results!r}"
                logger.error(err); self.log.emit(err); self.finished.emit(False, err); return
            done+=1; self.progress.emit(int(5 + (done/total)*15))

            if self._stop: self.finished.emit(False,"Canceled"); return
            msg=f"Configuring camera sensor registers at position {pos+1}…"
            logger.info(msg); self.log.emit(msg)
            cfg = self.interface.run_on_sensors("camera_configure_registers", camera_position=cam_mask_single)
            if not cfg:
                err=f"camera_configure_registers failed at position {pos+1}: {cfg!r}"
                logger.error(err); self.log.emit(err); self.finished.emit(False, err); return
            done+=1; self.progress.emit(int(5 + (done/total)*15))
        logger.info("FPGAs programmed & registers configured")
        self.finished.emit(True, "")