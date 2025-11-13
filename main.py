import sys
import os
import asyncio
import argparse
import warnings
import logging

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication          # <-- use QApplication
from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from qasync import QEventLoop

from motion_connector import MOTIONConnector
from pathlib import Path
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # or INFO depending on what you want to see

# Suppress PyQt6 DeprecationWarnings related to SIP
warnings.simplefilter("ignore", DeprecationWarning)

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

    app = QApplication(sys.argv) 

    # Set the global application icon
    app.setWindowIcon(QIcon("assets/images/favicon.png"))
    engine = QQmlApplicationEngine()

    # Expose to QML
    connector = MOTIONConnector(advanced_sensors=True)
    qmlRegisterSingletonInstance("OpenMotion", 1, 0, "MOTIONInterface", connector)
    engine.rootContext().setContextProperty("AppFlags", {
        "advancedSensors": True
    })
    engine.rootContext().setContextProperty("appVersion", "0.3.8d")

    # Load the QML file
    engine.load(resource_path("main.qml"))

    if not engine.rootObjects():
        print("Error: Failed to load QML file")
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
