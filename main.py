import sys
import os
import asyncio
import argparse
import warnings
import logging
import datetime

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication   
from PyQt6.QtWidgets import QApplication   
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from qasync import QEventLoop

from motion_connector import MOTIONConnector
from pathlib import Path


APP_VERSION = "0.4.1"


logger = logging.getLogger("bloodflow-app")
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
    logger.log(log_level, qml_message)

def resource_path(rel: str) -> str:
    import sys, os
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(sys.executable if getattr(sys,"frozen",False) else __file__)))
    return os.path.join(base, rel)

def main():
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"
    os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"] = "Dark"
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

    # --- parse flags ignore unknown (Qt) flags ---
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--advanced-sensors", action="store_true")
    my_args, _unknown = parser.parse_known_args(sys.argv[1:])

    # Configure logging
    logger.propagate = True

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
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
        "advancedSensors": True
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
        loop.close()

if __name__ == "__main__":
    main()
