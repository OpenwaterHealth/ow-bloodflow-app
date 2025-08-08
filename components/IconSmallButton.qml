import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

Item {
    id: iconSmallButton
    width: 24
    height: 24

    // Font icon properties
    property string iconGlyph: "\ue900"       // Unicode glyph for the icon
    property string buttonText: "Action"      // Tooltip text

    // Colors
    property color iconColor: "#BDC3C7"
    property color hoverColor: "#FFFFFF"
    property color backgroundColor: "#2C2C2E"
    property color hoverBackgroundColor: "#3E4E6F"
    property color borderColor: "transparent"
    property color hoverBorderColor: "#BDC3C7"

    // Signals
    signal clicked()

    // Load the icon font
    FontLoader {
        id: iconFont
        source: "../assets/fonts/keenicons-outline.ttf"
    }

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: 4
        color: mouseArea.containsMouse ? hoverBackgroundColor : backgroundColor
        border.color: mouseArea.containsMouse ? hoverBorderColor : borderColor
        border.width: 1
    }

    Text {
        id: iconText
        text: iconGlyph
        font.family: iconFont.name
        font.pixelSize: 16
        color: mouseArea.containsMouse ? hoverColor : iconColor
        anchors.centerIn: parent
    }

    // Tooltip
    Rectangle {
        id: tooltip
        visible: mouseArea.containsMouse
        opacity: mouseArea.containsMouse ? 1.0 : 0.0
        width: Math.max(80, buttonText.length * 8)
        height: 28
        radius: 4
        color: "#1C1C1E"
        border.color: "transparent"
        z: 10

        anchors {
            bottom: bg.top
            bottomMargin: 5
            horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: buttonText
            anchors.centerIn: parent
            font.pixelSize: 12
            color: "white"
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: iconSmallButton.clicked()
    }
}
