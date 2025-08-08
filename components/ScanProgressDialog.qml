import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 9999

    // API
    signal cancelRequested()
    property alias message: titleLabel.text
    property int progress: 0            // <-- bind from ScanRunner
    property string stageText: ""       // <-- bind from ScanRunner
    function open()  { root.visible = true }
    function close() { root.visible = false }
    function appendLog(line) {
        if (!line) return
        if (logArea.text.length > 0) logArea.text += "\n"
        logArea.text += line
        logArea.cursorPosition = logArea.length
    }

    // Dimmed backdrop
    Rectangle {
        anchors.fill: parent
        color: "#00000088"
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            onClicked: {}   // block clicks
        }
    }

    // Dialog panel
    Rectangle {
        id: panel
        width: 460
        height: 320
        radius: 10
        color: "#1E1E20"
        border.color: "#3E4E6F"
        border.width: 2
        anchors.centerIn: parent
        focus: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            // Title
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Layout.alignment: Qt.AlignHCenter

                Text {
                    id: titleLabel
                    text: "Scanning…"
                    color: "#FFFFFF"
                    font.pixelSize: 20
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            // Stage line
            Text {
                id: stageLine
                text: stageText.length ? stageText : "Preparing…"
                color: "#C9D1D9"
                font.pixelSize: 14
                wrapMode: Text.NoWrap
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            // Progress bar
            ProgressBar {
                id: prog
                from: 0; to: 100
                value: root.progress
                indeterminate: value < 5
                Layout.fillWidth: true
                Layout.preferredHeight: 8
            }

            // Animated dots
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 6
                Repeater {
                    model: 3
                    delegate: Rectangle {
                        width: 6; height: 6; radius: 3
                        color: "#4A90E2"
                        opacity: 0.3

                        SequentialAnimation on opacity {
                            running: root.visible
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.3; to: 1.0; duration: 400 }
                            NumberAnimation { from: 1.0; to: 0.3; duration: 400 }
                            onStarted: delay.start()
                        }
                        PauseAnimation { id: delay; duration: index * 120 }
                    }
                }
            }

            // Log area
            Frame {
                Layout.fillWidth: true
                Layout.fillHeight: true
                background: Rectangle { color: "#141417"; radius: 6; border.color: "#2B2B35" }
                ScrollView {
                    anchors.fill: parent
                    TextArea {
                        id: logArea
                        readOnly: true
                        wrapMode: TextEdit.NoWrap
                        text: ""
                        color: "#C9D1D9"
                        font.family: "Consolas"
                        font.pixelSize: 12
                        background: null
                    }
                }
            }

            // Buttons
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 12
                Button {
                    text: "Cancel Scan"
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 40
                    hoverEnabled: true
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: 16
                        color: "#BDC3C7"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: parent.hovered ? "#4A90E2" : "#3A3F4B"
                        border.color: parent.hovered ? "#FFFFFF" : "#BDC3C7"
                        radius: 6
                    }
                    onClicked: root.cancelRequested()
                }
            }
        }

        // ESC to cancel (no arrow funcs in QML)
        Keys.onReleased: function(event) {
            if (event.key === Qt.Key_Escape) {
                root.cancelRequested()
                event.accepted = true
            }
        }
    }
}
