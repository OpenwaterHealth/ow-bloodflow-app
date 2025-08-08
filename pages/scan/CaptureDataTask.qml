// qml/scan/CaptureDataTask.qml
import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property int cameraMask: 0x03
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

    function run() {
        if (!connector) { finished(false, "No connector"); return }
        started()
        progress(25)
        log("Capturing data… (" + durationSec + "s)")

        const onLog = (s)=> log(s)
        const onProg = (p)=> progress(Math.max(25, p))
        const onDone = (l, r)=> { leftPath = l; rightPath = r; cleanup(); finished(true, "") }
        const onErr = (msg)=> { cleanup(); finished(false, msg) }
        const onCancel = ()=> { cleanup(); finished(false, "Capture canceled") }

        function cleanup(){
            if (connector.log.connected(onLog)) connector.log.disconnect(onLog)
            if (connector.captureProgress.connected(onProg)) connector.captureProgress.disconnect(onProg)
            if (connector.captureFinished.connected(onDone)) connector.captureFinished.disconnect(onDone)
            if (connector.captureError.connected(onErr)) connector.captureError.disconnect(onErr)
            if (connector.captureCanceled.connected(onCancel)) connector.captureCanceled.disconnect(onCancel)
        }

        connector.log.connect(onLog)
        connector.captureProgress.connect(onProg)
        connector.captureFinished.connect(onDone)
        connector.captureError.connect(onErr)
        connector.captureCanceled.connect(onCancel)

        connector.startCapture(cameraMask, durationSec, subjectId, dataDir, disableLaser)
    }

    function cancel() { if (connector) connector.cancelCapture() }
}
