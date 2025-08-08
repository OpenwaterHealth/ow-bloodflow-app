// qml/scan/ScanRunner.qml
import QtQuick 6.5
import "."

QtObject {
    id: runner
    property var connector

    property int cameraMask: 0x03
    property int durationSec: 60
    property string subjectId: ""
    property string dataDir: ""
    property bool disableLaser: false
    property bool laserOn: true
    property int laserPower: 50
    property var triggerConfig: ({})

    signal stageUpdate(string stage)
    signal progressUpdate(int pct)
    signal messageOut(string text)
    signal scanFinished(bool ok, string error, string leftPath, string rightPath)

    property FlashSensorsTask flashTask: FlashSensorsTask {
        connector: runner.connector
        cameraMask: runner.cameraMask
        onStarted: stageUpdate("Configuring sensors/FPGA…")
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            if (!ok) { scanFinished(false, err, "", ""); return }
            setTask.run()
        }
    }

    property SetTriggerLaserTask setTask: SetTriggerLaserTask {
        connector: runner.connector
        laserOn: runner.laserOn
        triggerConfig: runner.triggerConfig
        onStarted: stageUpdate("Setting trigger & laser…")
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            if (!ok) { scanFinished(false, err, "", ""); return }
            capTask.run()
        }
    }

    property CaptureDataTask capTask: CaptureDataTask {
        connector: runner.connector
        cameraMask: runner.cameraMask
        durationSec: runner.durationSec
        subjectId: runner.subjectId
        dataDir: runner.dataDir
        disableLaser: runner.disableLaser
        onStarted: stageUpdate("Capturing…")
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            scanFinished(ok, err, ok ? leftPath : "", ok ? rightPath : "")
        }
    }

    function start() {
        console.log("Start Scan runner");
        stageUpdate("Preparing…");
        progressUpdate(1);
        messageOut("ScanRunner: start()");
        flashTask.run();
    }

    function cancel() {
        // stop flash, if your connector supports it
        if (connector && connector.cancelConfigureCameraSensors) {
            try { connector.cancelConfigureCameraSensors() } catch(e) {}
        }
        // stop trigger if capture running
        if (connector && connector.stopTrigger) {
            try { connector.stopTrigger() } catch(e) {}
        }
        // tell the UI we're done (not ok)
        scanFinished(false, "Canceled", "", "")
    }
}
