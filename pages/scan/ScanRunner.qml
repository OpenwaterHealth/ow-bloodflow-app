// qml/scan/ScanRunner.qml
import QtQuick 6.5
import "."

QtObject {
    id: runner
    property var connector


    property int leftMask: 0x00
    property int rightMask: 0x00

    property int cameraMask: 0x5A
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

    // --- Flash ---
    property FlashSensorsTask flashTask: FlashSensorsTask {
        connector: runner.connector
        cameraMask: runner.cameraMask

        property var _wd: null

        onStarted: {
            runner._stage = "flash"
            stageUpdate("Configuring sensors/FPGA…")
            // watchdog ~180s (your log showed ~50s)
            if (_wd) try { _wd.stop() } catch(e) {}
            _wd = Qt.createQmlObject('import QtQuick 6.5; Timer { interval: 180000; repeat: false }', flashTask, "flashWD")
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

    // --- Set trigger/laser ---
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

    // --- Capture ---
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
            if (!ok) { runner._finish(false, err, "", ""); return }
            // Capture OK → Post-process
            runner._stage = "post"
            stageUpdate("Post-processing…")
            postTask.leftPath  = leftPath
            postTask.rightPath = rightPath
            postTask.run()
        }
    }

    // --- Post-process (raw → csv) ---
    property PostProcessTask postTask: PostProcessTask {
        connector: runner.connector
        property var _wd: null
        onStarted: {
            // generous watchdog (depends on file size); adjust as needed
            if (_wd) try { _wd.stop() } catch(e) {}
            _wd = Qt.createQmlObject('import QtQuick 6.5; Timer { interval: 180000; repeat: false }', postTask, "postWD")
            _wd.triggered.connect(function() {
                messageOut("Post-processing timed out.")
                runner._finish(false, "Post-processing timed out", "", "")
            })
            _wd.start()
        }
        onProgress: function(pct) { progressUpdate(Math.max(95, Math.min(99, pct))) }
        onLog: function(line) { messageOut(line) }
        onFinished: function(ok, err, leftCsv, rightCsv) {
            if (_wd) { try { _wd.stop() } catch(e) {} _wd = null }
            if (!ok) { runner._finish(false, err, "", ""); return }
            // All done
            progressUpdate(100)
            stageUpdate("Scan complete")
            runner._finish(true, "", leftCsv, rightCsv)
        }
    }

    // controls
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
        switch (runner._stage) {
        case "flash":
            if (connector && connector.cancelConfigureCameraSensors)
                try { connector.cancelConfigureCameraSensors() } catch(e) {}
            break
        case "capture":
            if (connector && connector.stopCapture)
                try { connector.stopCapture() } catch(e) {}
            else if (connector && connector.stopTrigger)
                try { connector.stopTrigger() } catch(e) {}
            break
        case "post":
            if (connector && connector.cancelPostProcess)
                try { connector.cancelPostProcess() } catch(e) {}
            break
        }
        runner._finish(false, "Canceled", "", "")
    }
}
