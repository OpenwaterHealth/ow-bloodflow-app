// qml/scan/FlashSensorsTask.qml
import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property int leftCameraMask: 0x00
    property int rightCameraMask: 0x00

    signal started()
    signal progress(int pct)
    signal log(string line)
    signal finished(bool ok, string error)

    // keep local refs so we can disconnect safely
    property var _onLog: null
    property var _onProg: null
    property var _onDone: null

    function run() {
        if (!connector || !connector.startConfigureCameraSensors) {
            console.log("FlashSensorsTask: connector missing startConfigureCameraSensors()")
            finished(false, "No connector")
            return
        }

        started()
        progress(5)
        log("Configuring sensors/FPGA… (mask=0x" + leftCameraMask.toString(16).toUpperCase() + ")")

        // connect temp signals
        _onLog = function(s) { log(s) }
        _onProg = function(p) { progress(Math.max(5, p)) }
        _onDone = function(ok, err) {
            // cleanup connections
            try { connector.configLog.disconnect(_onLog) } catch(e) {}
            try { connector.configProgress.disconnect(_onProg) } catch(e) {}
            try { connector.configFinished.disconnect(_onDone) } catch(e) {}
            finished(ok, err || "")
        }

        connector.configLog.connect(_onLog)
        connector.configProgress.connect(_onProg)
        connector.configFinished.connect(_onDone)

        // start async; returns immediately so UI can render dialog
        connector.startConfigureCameraSensors(leftCameraMask, rightCameraMask)
        log("done1")
    }
}
