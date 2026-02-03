import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0
import QtQuick.Window 6.0
import OpenMotion 1.0

Window {
    id: meanWindow
    width: 900
    height: 520
    visible: false
    title: "Realtime Image Mean"
    color: "#1E1E20"

    property int windowSeconds: 15
    property bool running: false
    property var seriesData: ({})
    property var seriesOrder: []
    property var seriesColors: ({})
    property real latestTimestamp: 0
    property string plotMetric: "mean" // "mean" or "bfi"

    onPlotMetricChanged: {
        reset()
    }

    property var _palette: [
        "#4A90E2", "#E67E22", "#2ECC71", "#9B59B6",
        "#E74C3C", "#1ABC9C", "#F1C40F", "#95A5A6",
        "#3498DB", "#D35400", "#27AE60", "#8E44AD",
        "#C0392B", "#16A085", "#F39C12", "#7F8C8D"
    ]

    function _seriesKey(side, camId) {
        return side + ":" + camId
    }

    function _labelFor(key) {
        const parts = key.split(":")
        if (parts.length !== 2) return key
        const side = parts[0]
        const cam = parts[1]
        return (side === "left" ? "L" : "R") + "-" + cam
    }

    function _ensureSeries(key) {
        if (seriesData[key] !== undefined)
            return
        seriesData[key] = []
        seriesOrder.push(key)
        const colorIndex = (seriesOrder.length - 1) % _palette.length
        seriesColors[key] = _palette[colorIndex]
    }

    function _addMaskSeries(side, mask) {
        for (let bit = 0; bit < 8; bit++) {
            if (mask & (1 << bit)) {
                _ensureSeries(_seriesKey(side, bit))
            }
        }
    }

    function reset() {
        seriesData = ({})
        seriesOrder = []
        seriesColors = ({})
        latestTimestamp = 0
    }

    function startScan(leftMask, rightMask) {
        reset()
        running = true
        _addMaskSeries("left", leftMask)
        _addMaskSeries("right", rightMask)
        visible = true
        raise()
        requestActivate()
    }

    function stopScan() {
        running = false
    }

    function handleSample(side, camId, timestampSec, meanVal) {
        if (!running)
            return
        const key = _seriesKey(side, camId)
        _ensureSeries(key)
        seriesData[key].push({ t: timestampSec, v: meanVal })
        if (timestampSec > latestTimestamp) {
            latestTimestamp = timestampSec
        }
    }

    function _pruneAndRepaint() {
        if (!visible)
            return
        const nowTs = latestTimestamp > 0 ? latestTimestamp : (Date.now() / 1000.0)
        const cutoff = nowTs - windowSeconds
        for (let i = 0; i < seriesOrder.length; i++) {
            const key = seriesOrder[i]
            const series = seriesData[key] || []
            while (series.length > 0 && series[0].t < cutoff) {
                series.shift()
            }
        }
        plotCanvas.requestPaint()
    }

    onClosing: {
        running = false
    }

    Timer {
        interval: 100
        repeat: true
        running: meanWindow.visible
        onTriggered: meanWindow._pruneAndRepaint()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: (plotMetric === "bfi" ? "BFI" : "Image Mean") + " (Last " + windowSeconds + "s)"
                color: "#FFFFFF"
                font.pixelSize: 16
            }

            Item { Layout.fillWidth: true }

            RowLayout {
                spacing: 6
                Text {
                    text: "Mean"
                    color: "#BDC3C7"
                    font.pixelSize: 12
                }
                Switch {
                    id: metricSwitch
                    checked: plotMetric === "bfi"
                    onToggled: plotMetric = checked ? "bfi" : "mean"
                }
                Text {
                    text: "BFI"
                    color: "#BDC3C7"
                    font.pixelSize: 12
                }
            }

            Repeater {
                model: seriesOrder
                delegate: RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: seriesColors[modelData] || "#BDC3C7"
                    }
                    Text {
                        text: meanWindow._labelFor(modelData)
                        color: "#BDC3C7"
                        font.pixelSize: 12
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#1E1E20"
            border.color: "#3E4E6F"
            radius: 6

            Canvas {
                id: plotCanvas
                anchors.fill: parent
                anchors.margins: 12
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    const pad = 36
                    const w = width - 2 * pad
                    const h = height - 2 * pad
                    if (w <= 0 || h <= 0)
                        return

                    const nowTs = meanWindow.latestTimestamp > 0 ? meanWindow.latestTimestamp : (Date.now() / 1000.0)
                    const xMin = nowTs - meanWindow.windowSeconds
                    const xMax = nowTs

                    let maxVal = -Infinity
                    let minVal = Infinity
                    for (let i = 0; i < meanWindow.seriesOrder.length; i++) {
                        const key = meanWindow.seriesOrder[i]
                        const series = meanWindow.seriesData[key] || []
                        for (let j = 0; j < series.length; j++) {
                            if (series[j].v > maxVal)
                                maxVal = series[j].v
                            if (series[j].v < minVal)
                                minVal = series[j].v
                        }
                    }
                    if (!isFinite(minVal) || !isFinite(maxVal)) {
                        minVal = 0
                        maxVal = 1
                    } else if (minVal === maxVal) {
                        minVal = minVal - 1
                        maxVal = maxVal + 1
                    }
                    const yRange = maxVal - minVal

                    // Axes
                    ctx.strokeStyle = "#BDC3C7"
                    ctx.lineWidth = 1
                    ctx.beginPath()
                    ctx.moveTo(pad, pad)
                    ctx.lineTo(pad, pad + h)
                    ctx.lineTo(pad + w, pad + h)
                    ctx.stroke()

                    // X-axis labels
                    ctx.fillStyle = "#BDC3C7"
                    ctx.font = "11px sans-serif"
                    ctx.textAlign = "left"
                    ctx.fillText("-" + meanWindow.windowSeconds + "s", pad, pad + h + 18)
                    ctx.textAlign = "right"
                    ctx.fillText("now", pad + w, pad + h + 18)

                    // Y-axis label
                    ctx.save()
                    ctx.translate(12, pad + h / 2)
                    ctx.rotate(-Math.PI / 2)
                    ctx.textAlign = "center"
                    ctx.fillText(meanWindow.plotMetric === "bfi" ? "BFI" : "Mean", 0, 0)
                    ctx.restore()

                    // Series lines
                    for (let i = 0; i < meanWindow.seriesOrder.length; i++) {
                        const key = meanWindow.seriesOrder[i]
                        const series = meanWindow.seriesData[key] || []
                        if (series.length < 2)
                            continue
                        ctx.strokeStyle = meanWindow.seriesColors[key] || "#4A90E2"
                        ctx.lineWidth = 2
                        ctx.beginPath()
                        for (let j = 0; j < series.length; j++) {
                            const pt = series[j]
                            const x = pad + ((pt.t - xMin) / (xMax - xMin)) * w
                            const y = pad + h - ((pt.v - minVal) / yRange) * h
                            if (j === 0)
                                ctx.moveTo(x, y)
                            else
                                ctx.lineTo(x, y)
                        }
                        ctx.stroke()
                    }

                    if (meanWindow.seriesOrder.length === 0) {
                        ctx.fillStyle = "#7F8C8D"
                        ctx.textAlign = "center"
                        ctx.fillText("Waiting for data...", pad + w / 2, pad + h / 2)
                    }
                }
            }
        }
    }

    Connections {
        target: MOTIONInterface
        function onScanMeanSampled(side, camId, timestampSec, meanVal) {
            if (meanWindow.plotMetric === "mean") {
                meanWindow.handleSample(side, camId, timestampSec, meanVal)
            }
        }
        function onScanBfiSampled(side, camId, timestampSec, bfiVal) {
            if (meanWindow.plotMetric === "bfi") {
                meanWindow.handleSample(side, camId, timestampSec, bfiVal)
            }
        }
    }
}
