import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0
import QtQuick.Controls as Controls

Rectangle {
    id: root
    property string title: "Sensor"
    property int circleSize: 20
    property var sensorActive: [false, false, false, false, false, false, false, false]
    property bool fanOn: false
    property string sensorSide: "left"  // "left" or "right"
    property var connector

    width: 200
    height: 260
    radius: 10
    color: "#1E1E20"
    border.color: "#3E4E6F"
    border.width: 2

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        Text {
            text: root.title
            font.pixelSize: 16
            color: "#BDC3C7"
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        GridLayout {
            columns: 3
            columnSpacing: 20
            rowSpacing: 10
            Layout.alignment: Qt.AlignHCenter

            // Row 1
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[7] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }
            Item {}
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[0] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }

            // Row 2
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[6] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }
            Item {}
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[1] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }

            // Row 3
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[5] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }
            Item {}
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[2] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }

            // Row 4
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[4] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }
            Item {}
            Rectangle { width: circleSize; height: circleSize; radius: circleSize/2
                color: sensorActive[3] ? "#4A90E2" : "#666666"; border.color: "black"; border.width: 1 }

            // Row 5 - Laser
            Item {}
            Rectangle {
                width: circleSize; height: circleSize; radius: circleSize/2
                color: "#FFD700"  // Yellow laser
                border.color: "black"; border.width: 1
            }
            Item {}
        }

    }
    
    // Fan Control CheckBox - positioned in top right corner
    CheckBox {
        id: fanButton
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 12
        anchors.rightMargin: 0
        checked: root.fanOn
        hoverEnabled: true
        
        indicator: Image {
            source: "../assets/images/icons8-fan-30.png"
            width: 30
            height: 30
            opacity: parent.checked ? 1.0 : 0.5
            anchors.left: parent.left
            anchors.leftMargin: 10
        }
        
        onToggled: {
            // Toggle fan state
            var newFanState = checked
            if (connector) {
                var success = connector.setFanControl(root.sensorSide, newFanState)
                if (success) {
                    root.fanOn = newFanState
                } else {
                    console.log("Failed to toggle fan for", root.sensorSide, "sensor")
                }
            } else {
                console.log("MotionInterface not available")
            }
        }
    }
    
    // Initialize fan status when component loads
    Component.onCompleted: {
        if (connector) {
            root.fanOn = connector.getFanControlStatus(root.sensorSide)
        }
    }
}
