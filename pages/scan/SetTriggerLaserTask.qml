// qml/scan/SetTriggerLaserTask.qml
import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property bool laserOn: true
    property var triggerConfig: ({})     // extra fields merged into payload
    property bool applyLaserPowerFromConfig: true  // toggle for testing

    signal started()
    signal progress(int pct)
    signal log(string line)
    signal finished(bool ok, string error)

    function run() {
        started()
        progress(20)
        log("Setting trigger & laser…")

        if (!connector || !connector.setTrigger || !connector.setLaserPowerFromConfig) {
            finished(false, "Connector missing setTrigger/setLaserPowerFromConfig")
            return
        }

        // Build payload for backend: 2=ON, 1=OFF
        var payload = { "TriggerStatus": laserOn ? 2 : 1 }
        for (var k in triggerConfig) payload[k] = triggerConfig[k]

        // Set trigger
        try {
            var res = connector.setTrigger(JSON.stringify(payload))
            var ok = (typeof res === "boolean") ? res : true
            if (!ok) {
                log("setTrigger returned false")
                finished(false, "setTrigger returned false")
                return
            }
            log("Trigger set.")
        } catch (e) {
            log("setTrigger exception: " + e)
            finished(false, "setTrigger exception: " + e)
            return
        }

        // Optionally apply laser power from config
        if (applyLaserPowerFromConfig) {
            progress(23)
            try {
                var res2 = connector.setLaserPowerFromConfig()
                var ok2 = (typeof res2 === "boolean") ? res2 : true
                if (!ok2) {
                    log("setLaserPowerFromConfig returned false")
                    finished(false, "setLaserPowerFromConfig returned false")
                    return
                }
                log("Laser power applied from config.")
            } catch (e2) {
                log("setLaserPowerFromConfig exception: " + e2)
                finished(false, "setLaserPowerFromConfig exception: " + e2)
                return
            }
        }

        progress(25)
        finished(true, "")
    }
}
