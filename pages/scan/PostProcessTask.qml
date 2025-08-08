import QtQuick 6.5

QtObject {
    id: task
    property var connector
    property string leftPath: ""
    property string rightPath: ""

    signal started()
    signal progress(int pct)
    signal log(string line)
    signal finished(bool ok, string error, string leftCsv, string rightCsv)

    function run() {
        if (!connector || !connector.startPostProcess) {
            finished(false, "Connector missing startPostProcess()", "", "")
            return
        }
        started()
        progress(1)
        log("Post-processing raw → CSV…")

        // wire up connector signals
        const onProg = (p)=> progress(p)
        const onLog  = (s)=> log(s)
        const onDone = function(ok, err, lcsv, rcsv) {
            try {
                connector.postProgress.disconnect(onProg)
                connector.postLog.disconnect(onLog)
                connector.postFinished.disconnect(onDone)
            } catch(e) {}
            finished(ok, err || "", lcsv || "", rcsv || "")
        }

        connector.postProgress.connect(onProg)
        connector.postLog.connect(onLog)
        connector.postFinished.connect(onDone)

        // kick it off (async thread in backend)
        try {
            const kicked = connector.startPostProcess(leftPath, rightPath)
            if (!kicked) {
                // backend refused to start (already running etc.)
                onDone(false, "startPostProcess() returned false", "", "")
            }
        } catch (e) {
            onDone(false, "startPostProcess exception: " + e, "", "")
        }
    }
}
