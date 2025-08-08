// qml/scan/SetTriggerLaserTask.qml
import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property bool laserOn: true
    property int laserPower: 50
    property var triggerConfig: ({
        "frequencyHz": 200,
        "pulseCount": 10,
        "pulseWidthUsec": 2000,
        "trainIntervalMs": 1000,
        "trainCount": 1,
        "mode": "single"
    })

    signal started()
    signal progress(int pct)
    signal log(string line)
    signal finished(bool ok, string error)

    function run() {
        if (!connector) { finished(false, "No connector"); return }
        started()
        progress(20)
        log("Setting trigger & laser…")

        const onLog = (s)=> log(s)
        const onProg = (p)=> progress(Math.max(20, p))
        const onDone = (ok, err)=> {
            connector.log.disconnect(onLog)
            connector.taskProgress.disconnect(onProg)
            connector.taskDone.disconnect(onDone)
            finished(ok, err || "")
        }

        connector.log.connect(onLog)
        connector.taskProgress.connect(onProg)
        connector.taskDone.connect(onDone)

        connector.setTriggerAndLaser(laserOn, laserPower, triggerConfig)
    }
}
