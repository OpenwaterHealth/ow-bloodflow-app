// components/ScanProgressDialog.qml
import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 9999    // float above everything

    // API
    signal cancelRequested()
    property alias message: scanLabel.text
    function open()  { root.visible = true;}
    function close() { root.visible = false;}

    // Dimmed backdrop (clicks blocked)
    Rectangle {
        anchors.fill: parent
        color: "#00000088"

        // Catch all mouse/touch events so background UI can't interact
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            onClicked: {}   // do nothing, just block
        }
    }

    // Dialog panel
    Rectangle {
        id: panel
        width: 360
        height: 200
        radius: 10
        color: "#1E1E20"
        border.color: "#3E4E6F"
        border.width: 2
        anchors.centerIn: parent

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Layout.alignment: Qt.AlignHCenter

                Text {
                    id: scanLabel
                    text: "Scanning"
                    color: "#FFFFFF"
                    font.pixelSize: 20
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            // Tiny animated dots below for extra feedback
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
                            // Stagger each dot
                            onStarted: pauseAnimation.start()
                        }
                        PauseAnimation {
                            id: pauseAnimation
                            duration: index * 120
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 12

                Button {
                    text: "Cancel Scan"
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 48
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
                        radius: 4
                    }

                    onClicked: root.cancelRequested()
                }
            }
        }

        // ESC to cancel
        Keys.onReleased: (event) => {
            if (event.key === Qt.Key_Escape) {
                root.cancelRequested()
                event.accepted = true
            }
        }
        focus: true
    }
}
