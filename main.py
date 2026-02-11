import sys
import os
import asyncio
import argparse
import warnings
import logging
import datetime
import atexit
import tempfile

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from qasync import QEventLoop

from motion_connector import MOTIONConnector
from pathlib import Path


APP_VERSION = "0.4.3"


logger = logging.getLogger("openmotion.bloodflow-app")
logger.setLevel(logging.INFO)  # or INFO depending on what you want to see

# Suppress PyQt6 DeprecationWarnings related to SIP
warnings.simplefilter("ignore", DeprecationWarning)

# Wire up the things that get logged out of QT app to the proper logs
def qt_message_handler(msg_type, context, message):
    """Custom Qt message handler to forward QML console.log() messages to the run log."""
    # Map Qt message types to logging levels
    log_level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    
    # Get the logging level (default to INFO for console.log)
    log_level = log_level_map.get(msg_type, logging.INFO)
    
    qml_message = f"QML: {message}"
    
    logger = logging.getLogger("openmotion.bloodflow-app.qml-console")
    logger.setLevel(logging.INFO)  # or INFO depending on what you want to see
    logger.info(qml_message)

def resource_path(rel: str) -> str:
    import sys, os
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(sys.executable if getattr(sys,"frozen",False) else __file__)))
    return os.path.join(base, rel)

# Single-instance lock management
_lock_file = None
_mutex = None

def check_single_instance():
    """Check if another instance is already running. Returns True if this is the first instance."""
    global _lock_file, _mutex
    
    app_name = "OpenWaterBloodflowApp"
    
    if sys.platform == "win32":
        # Use named mutex on Windows
        try:
            import ctypes
            from ctypes import wintypes
            
            # Create a named mutex
            mutex_name = f"Global\\{app_name}"
            _mutex = ctypes.windll.kernel32.CreateMutexW(
                None,  # Default security attributes
                True,  # Initial owner
                mutex_name
            )
            
            # Check if mutex already exists (GetLastError returns ERROR_ALREADY_EXISTS)
            last_error = ctypes.windll.kernel32.GetLastError()
            
            if last_error == 183:  # ERROR_ALREADY_EXISTS
                # Another instance is running
                ctypes.windll.kernel32.CloseHandle(_mutex)
                _mutex = None
                return False
            
            # Register cleanup function
            atexit.register(cleanup_single_instance)
            return True
            
        except Exception as e:
            # Logging may not be configured yet, so use print as fallback
            try:
                logger.warning(f"Failed to create mutex: {e}. Falling back to file lock.")
            except:
                print(f"Warning: Failed to create mutex: {e}. Falling back to file lock.")
            # Fall through to file-based lock
    
    # Fallback: Use lock file (cross-platform)
    try:
        lock_dir = tempfile.gettempdir()
        lock_file_path = os.path.join(lock_dir, f"{app_name}.lock")
        
        # Try to create lock file exclusively
        try:
            _lock_file = open(lock_file_path, 'x')  # 'x' mode creates file exclusively
            _lock_file.write(str(os.getpid()))
            _lock_file.flush()
            
            # Register cleanup function
            atexit.register(cleanup_single_instance)
            return True
            
        except FileExistsError:
            # Lock file exists - check if process is still running
            try:
                with open(lock_file_path, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is still running
                if sys.platform == "win32":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    # PROCESS_QUERY_LIMITED_INFORMATION (0x1000) - safer than PROCESS_QUERY_INFORMATION
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return False  # Process is still running
                    else:
                        # Process doesn't exist, remove stale lock file
                        try:
                            os.remove(lock_file_path)
                            # Try to create our own lock file
                            _lock_file = open(lock_file_path, 'x')
                            _lock_file.write(str(os.getpid()))
                            _lock_file.flush()
                            atexit.register(cleanup_single_instance)
                            return True
                        except Exception:
                            return False
                else:
                    # Unix-like: check if process exists
                    try:
                        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                        return False  # Process is still running
                    except ProcessLookupError:
                        # Process doesn't exist, remove stale lock file
                        try:
                            os.remove(lock_file_path)
                            _lock_file = open(lock_file_path, 'x')
                            _lock_file.write(str(os.getpid()))
                            _lock_file.flush()
                            atexit.register(cleanup_single_instance)
                            return True
                        except Exception:
                            return False
            except (ValueError, OSError):
                # Lock file is corrupted or unreadable
                try:
                    os.remove(lock_file_path)
                    _lock_file = open(lock_file_path, 'x')
                    _lock_file.write(str(os.getpid()))
                    _lock_file.flush()
                    atexit.register(cleanup_single_instance)
                    return True
                except Exception:
                    return False
                    
    except Exception as e:
        # Logging may not be configured yet, so use print as fallback
        try:
            logger.error(f"Failed to create lock file: {e}")
        except:
            print(f"Error: Failed to create lock file: {e}")
        return False

def cleanup_single_instance():
    """Clean up the single-instance lock."""
    global _lock_file, _mutex
    
    if _mutex:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_mutex)
            _mutex = None
        except Exception:
            pass
    
    if _lock_file:
        try:
            lock_file_path = _lock_file.name
            _lock_file.close()
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
            _lock_file = None
        except Exception:
            pass

def main():
    # Check if another instance is already running
    if not check_single_instance():
        # Create a minimal QApplication to show message box
        app = QApplication(sys.argv)
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("OpenWater Bloodflow")
        msg_box.setText("Another instance of the application is already running.")
        msg_box.setInformativeText("Please close the existing instance before opening a new one.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        sys.exit(1)
    
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"
    os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"] = "Dark"
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

    # --- parse flags ignore unknown (Qt) flags ---
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--advanced-sensors", action="store_true")
    my_args, _unknown = parser.parse_known_args(sys.argv[1:])

    # Configure logging
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    #Configure console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    #Configure file logging
    run_dir = os.path.join(os.getcwd(), "app-logs") # Also add file handler for local logging
    os.makedirs(run_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") # Build timestamp like 20251029_124455
    logfile_path = os.path.join(run_dir, f"ow-bloodflowapp-{ts}.log")

    file_handler = logging.FileHandler(logfile_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f"logging to {logfile_path}")
    
    # Configure the SDK logger hierarchy to use the same handlers
    sdk_logger = logging.getLogger("openmotion.sdk")
    sdk_logger.setLevel(logging.INFO)
    sdk_logger.addHandler(console_handler)
    sdk_logger.addHandler(file_handler)
    sdk_logger.propagate = False  # Don't propagate to root, use our handlers

    qInstallMessageHandler(qt_message_handler)
    
    app = QApplication(sys.argv) 
        
    # Windows-specific: Set application user model ID for proper taskbar grouping
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenWaterHealth.BloodflowApp")
        except Exception:
            pass  # Ignore if not available
    
    icon_path = resource_path("assets/images/favicon.ico")
    app.setWindowIcon(QIcon(icon_path))
    
    # Set application properties for Windows taskbar
    app.setApplicationName("OpenWater Bloodflow")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("OpenWater Health")
    
    engine = QQmlApplicationEngine()

    # Expose to QML
    connector = MOTIONConnector(advanced_sensors=True)
    qmlRegisterSingletonInstance("OpenMotion", 1, 0, "MOTIONInterface", connector)
    engine.rootContext().setContextProperty("AppFlags", {
        "advancedSensors": True,
        "realtimePlotEnabled": False
    })
    engine.rootContext().setContextProperty("appVersion", APP_VERSION)

    # Load the QML file
    engine.load(resource_path("main.qml"))

    if not engine.rootObjects():
        logger.error("Error: Failed to load QML file")
        sys.exit(-1)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    async def main_async():
        logger.info("Starting MOTION monitoring...")
        await connector._interface.start_monitoring()

    async def shutdown():
        logger.info("Shutting down MOTION monitoring...")
        connector._interface.stop_monitoring()

        pending_tasks = [t for t in asyncio.all_tasks() if not t.done()]
        if pending_tasks:
            logger.info(f"Cancelling {len(pending_tasks)} pending tasks...")
            for task in pending_tasks:
                task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        logger.info("LIFU monitoring stopped. Application shutting down.")

    def handle_exit():
        logger.info("Application closing...")
        asyncio.ensure_future(shutdown()).add_done_callback(lambda _: loop.stop())
        engine.deleteLater()  # Ensure QML engine is destroyed
        cleanup_single_instance()  # Clean up single-instance lock

    app.aboutToQuit.connect(handle_exit)

    try:
        with loop:
            loop.run_until_complete(main_async())
            loop.run_forever()
    except RuntimeError as e:
        if "Event loop stopped before Future completed" in str(e):
            logger.warning("App closed while a Future was still running (safe to ignore)")
        else:
            logger.error(f"Runtime error: {e}")
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    finally:
        #print out logger tree
        logger.info("Logger tree:")
        logger.info(logger.manager.loggerDict)
        loop.close()

if __name__ == "__main__":
    main()
