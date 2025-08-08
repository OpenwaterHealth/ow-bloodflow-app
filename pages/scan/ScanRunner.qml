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

    // internal
    property string _stage: "idle"
    property bool _done: false
    function _finish(ok, err, l, r) {
        if (_done) return
        _done = true
        scanFinished(ok, err || "", l || "", r || "")
        _stage = "idle"
    }

    property FlashSensorsTask flashTask: FlashSensorsTask {
        connector: runner.connector
        cameraMask: runner.cameraMask

        property var _wd: null

        onStarted: {
            runner._stage = "flash"
            stageUpdate("Configuring sensors/FPGA…")
            // watchdog ~70s (your log showed ~50s)
            if (_wd) try { _wd.stop() } catch(e) {}
            _wd = Qt.createQmlObject('import QtQuick 6.5; Timer { interval: 70000; repeat: false }', flashTask, "flashWD")
            _wd.triggered.connect(function() {
                messageOut("Flash step timed out.")
                runner._finish(false, "Flash step timed out", "", "")
            })
            _wd.start()
        }
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            if (_wd) { try { _wd.stop() } catch(e) {} _wd = null }
            if (!ok) { runner._finish(false, err, "", ""); return }
            setTask.run()
        }
    }

    property SetTriggerLaserTask setTask: SetTriggerLaserTask {
        connector: runner.connector
        laserOn: runner.laserOn
        triggerConfig: runner.triggerConfig

        property var _wd: null

        onStarted: {
            runner._stage = "set"
            stageUpdate("Setting trigger & laser…")
            // watchdog 5s (quick sync calls)
            if (_wd) try { _wd.stop() } catch(e) {}
            _wd = Qt.createQmlObject('import QtQuick 6.5; Timer { interval: 5000; repeat: false }', setTask, "setWD")
            _wd.triggered.connect(function() {
                messageOut("SetTrigger/Laser step timed out.")
                runner._finish(false, "SetTrigger/Laser step timed out", "", "")
            })
            _wd.start()
        }
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            if (_wd) { try { _wd.stop() } catch(e) {} _wd = null }
            if (!ok) { runner._finish(false, err, "", ""); return }
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
        onStarted: {
            runner._stage = "capture"
            stageUpdate("Capturing…")
        }
        onProgress: function(pct) { progressUpdate(pct) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err) {
            runner._finish(ok, err, ok ? leftPath : "", ok ? rightPath : "")
        }
    }

    function start() {
        if (runner._stage !== "idle") {
            messageOut("Scan already running, ignoring start()")
            return
        }
        _done = false
        progressUpdate(1)
        stageUpdate("Preparing…")
        messageOut("ScanRunner: start()")
        flashTask.run()
    }

    function cancel() {
        // stop flash (async worker) if running
        if (runner._stage === "flash" && connector && connector.cancelConfigureCameraSensors) {
            try { connector.cancelConfigureCameraSensors() } catch(e) {}
        }
        // stop capture trigger if running
        if (connector && connector.stopTrigger) {
            try { connector.stopTrigger() } catch(e) {}
        }
        runner._finish(false, "Canceled", "", "")
    }
}
