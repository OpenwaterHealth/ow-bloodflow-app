// qml/scan/CaptureDataTask.qml
import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property int leftCameraMask: 0x00
    property int rightCameraMask: 0x00
    property int durationSec: 60
    property string subjectId: ""
    property string dataDir: ""
    property bool disableLaser: false

    property string leftPath: ""
    property string rightPath: ""

    signal started()
    signal progress(int pct)
    signal log(string line)
    signal finished(bool ok, string error)

    property var _onLog: null
    property var _onProg: null
    property var _onDone: null

    function run() {
        if (!connector || !connector.startCapture) {
            finished(false, "Connector missing startCapture()")
            return
        }
        started()
        progress(25)
        log("Preparing capture…")

        // hook signals
        _onLog = function(s) { log(s) }
        _onProg = function(p) { progress(Math.max(25, p)) }
        _onDone = function(ok, err, left, right) {
            // cleanup
            try { connector.captureLog.disconnect(_onLog) } catch(e) {}
            try { connector.captureProgress.disconnect(_onProg) } catch(e) {}
            try { connector.captureFinished.disconnect(_onDone) } catch(e) {}

            leftPath = left || ""
            rightPath = right || ""
            finished(ok, err || "")
        }

        connector.captureLog.connect(_onLog)
        connector.captureProgress.connect(_onProg)
        connector.captureFinished.connect(_onDone)

        // kick off async capture
        var startedOk = false
        try {
            startedOk = connector.startCapture(subjectId, durationSec, leftCameraMask, rightCameraMask, dataDir, disableLaser)
        } catch(e) {}
        if (!startedOk) {
            // cleanup if start failed
            try { connector.captureLog.disconnect(_onLog) } catch(e) {}
            try { connector.captureProgress.disconnect(_onProg) } catch(e) {}
            try { connector.captureFinished.disconnect(_onDone) } catch(e) {}
            finished(false, "startCapture failed to start")
        }
    }

    function cancel() {
        if (connector && connector.stopCapture) {
            try { connector.stopCapture() } catch(e) {}
        }
        // finished(false, "Capture canceled") will be emitted by connector via captureFinished
    }
}
