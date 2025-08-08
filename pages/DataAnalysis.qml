import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0
import OpenMotion 1.0 

Rectangle {
    id: dataAnalysis
    width: parent.width
    height: parent.height
    color: "#29292B" // Background color for Page 1
    radius: 20
    opacity: 0.95 // Slight transparency for the content area


    // UI state
    property var scans: []          // ["owABCD12_20250808_120000", ...]
    property var selected: ({})     // {subjectId,timestamp,maskHex,leftPath,rightPath,notesPath,notes}

    signal requestOpenFolder(string folderPath)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "Data Analysis"
                font.pixelSize: 22
                color: "white"
                Layout.alignment: Qt.AlignVCenter
            }
            Item { Layout.fillWidth: true }

            
            Button {
                id: btnOpenFolder
                text: "Open Folder"
                Layout.preferredWidth: 120
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignRight
                hoverEnabled: enabled          

                contentItem: Text {
                    text: parent.text
                    font.pixelSize: 14
                    color: parent.enabled ? "#BDC3C7" : "#7F8C8D"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: !parent.enabled ? "#3A3F4B" : parent.hovered ? "#4A90E2" : "#3A3F4B"
                    border.color: !parent.enabled ? "#7F8C8D" : parent.hovered ? "#FFFFFF" : "#BDC3C7"
                    radius: 4
                }
                onClicked: {
                    requestOpenFolder(MOTIONInterface.directory)
                }
            }

            Button {
                id: btnRefresh
                text: "Refresh"
                Layout.preferredWidth: 120
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignRight
                hoverEnabled: enabled          

                contentItem: Text {
                    text: parent.text
                    font.pixelSize: 14
                    color: parent.enabled ? "#BDC3C7" : "#7F8C8D"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: !parent.enabled ? "#3A3F4B" : parent.hovered ? "#4A90E2" : "#3A3F4B"
                    border.color: !parent.enabled ? "#7F8C8D" : parent.hovered ? "#FFFFFF" : "#BDC3C7"
                    radius: 4
                }
                onClicked: {
                    refreshScans()
                }
            }
        }

        // Data directory display
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "Data Directory:"; color: "#BDC3C7"; font.pixelSize: 14 }
            Text {
                text: MOTIONInterface.directory
                color: "white"; font.pixelSize: 14
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // Scan selector
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text { text: "Scan:"; color: "#BDC3C7"; font.pixelSize: 16; Layout.alignment: Qt.AlignVCenter }

            ComboBox {
                id: scanPicker
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                model: scans
                // Each item in model is a string like "owIZGDFP_20250808_120740"
                delegate: ItemDelegate {
                    width: parent.width
                    text: modelData
                }
                onCurrentIndexChanged: {
                    if (currentIndex >= 0 && currentIndex < scans.length) {
                        const id = scans[currentIndex]
                        try {
                            selected = MOTIONInterface.get_scan_details(id) || {}
                        } catch (e) {
                            console.warn("get_scan_details failed:", e)
                            selected = {}
                        }
                    } else {
                        selected = {}
                    }
                }
            }
        }

        // --- Details + notes + actions ---
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: "#1E1E20"
            border.color: "#3E4E6F"
            border.width: 2

            RowLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 16

                // LEFT SIDE: metadata + notes
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: parent.width * 0.55
                    spacing: 12

                    // Metadata grid
                    GridLayout {
                        columns: 4
                        columnSpacing: 24
                        rowSpacing: 8
                        Layout.fillWidth: true

                        // Row 1: Subject / Date-Time
                        Text { text: "Subject ID:"; color: "#BDC3C7"; font.pixelSize: 14 }
                        Text { text: selected.subjectId || "-"; color: "white"; font.pixelSize: 14 }

                        Text { text: "Date/Time:"; color: "#BDC3C7"; font.pixelSize: 14 }
                        Text { text: selected.timestamp ? friendlyDate(selected.timestamp) : "-"; color: "white"; font.pixelSize: 14 }

                        // Row 2: (Mask under Date/Time)
                        Text { text: "Left File:"; color: "#BDC3C7"; font.pixelSize: 14 }
                        Text {
                            text: basename(selected.leftPath) || "(none)"
                            color: "white"; font.pixelSize: 12
                            elide: Text.ElideRight; Layout.fillWidth: true
                        }
                        Text { text: "Mask:"; color: "#BDC3C7"; font.pixelSize: 14 }
                        Text { text: selected.maskHex ? ("0x" + selected.maskHex.toUpperCase()) : "-"; color: "white"; font.pixelSize: 14 }

                        // Row 3: Left file (above Right file)
                        Text { text: "Right File:"; color: "#BDC3C7"; font.pixelSize: 14 }
                        Text {
                            text: basename(selected.rightPath) || "(none)"
                            color: "white"; font.pixelSize: 12
                            elide: Text.ElideRight; Layout.fillWidth: true
                        }
                        Text { text: ""; } // spacer under Subject label
                        Text { text: ""; } // spacer under Subject value
                    }

                    // Notes
                    Text { text: "Notes:"; color: "#BDC3C7"; font.pixelSize: 14 }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 6
                        color: "#2E2E33"
                        border.color: "#3E4E6F"
                        border.width: 1

                        ScrollView {
                            anchors.fill: parent
                            TextArea {
                                id: notesView
                                readOnly: true
                                wrapMode: Text.Wrap
                                text: selected.notes || ""
                                color: "white"
                                font.pixelSize: 14
                                background: null
                            }
                        }
                    }
                }

                // RIGHT SIDE: actions panel
                Rectangle {
                    Layout.preferredWidth: parent.width * 0.40
                    Layout.fillHeight: true
                    radius: 10
                    color: "#232329"
                    border.color: "#3E4E6F"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text { text: "Actions"; color: "white"; font.pixelSize: 16 }

                        Button {
                            id: btnPostProcess
                            text: "Post Processing"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            Layout.alignment: Qt.AlignHCenter 
                            enabled: !!(selected.leftPath || selected.rightPath)
                            hoverEnabled: enabled          

                            contentItem: Text {
                                text: parent.text
                                font.pixelSize: 14
                                color: parent.enabled ? "#BDC3C7" : "#7F8C8D"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: !parent.enabled ? "#3A3F4B" : parent.hovered ? "#4A90E2" : "#3A3F4B"
                                border.color: !parent.enabled ? "#7F8C8D" : parent.hovered ? "#FFFFFF" : "#BDC3C7"
                                radius: 4
                            }
                            onClicked: {
                                console.log("Post Process", selected.leftPath, selected.rightPath)
                            }
                        }

                        Button {
                            id: btnVisualize
                            text: "Visualize"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            Layout.alignment: Qt.AlignHCenter 
                            enabled: !!(selected.leftPath || selected.rightPath)
                            hoverEnabled: enabled          

                            contentItem: Text {
                                text: parent.text
                                font.pixelSize: 14
                                color: parent.enabled ? "#BDC3C7" : "#7F8C8D"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: !parent.enabled ? "#3A3F4B" : parent.hovered ? "#4A90E2" : "#3A3F4B"
                                border.color: !parent.enabled ? "#7F8C8D" : parent.hovered ? "#FFFFFF" : "#BDC3C7"
                                radius: 4
                            }
                            onClicked: {
                                console.log("Visualize", selected.leftPath, selected.rightPath)
                            }
                        }

                        // Spacer to push future content down if you add charts later
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }

    // Helpers (place in root component scope)
    function basename(p) {
        if (!p || p.length === 0) return ""
        // handle Windows paths
        const norm = p.replace(/\\/g, "/")
        const idx = norm.lastIndexOf("/")
        return idx >= 0 ? norm.slice(idx + 1) : norm
    }
    
    function refreshScans() {
        try {
            // backend returns ["owSUBJ_YYYYMMDD_HHMMSS", ...] sorted (you implemented this)
            scans = MOTIONInterface.get_scan_list() || []
            if (scans.length > 0) {
                scanPicker.currentIndex = 0
                selected = MOTIONInterface.get_scan_details(scans[0]) || {}
            } else {
                selected = {}
            }
        } catch (e) {
            console.warn("get_scan_list failed:", e)
            scans = []
            selected = {}
        }
    }

    function friendlyDate(ts) {
        if (!ts || ts.length !== 15) return ts || "-"
        const y = ts.slice(0,4), m = ts.slice(4,6), d = ts.slice(6,8)
        const hh = ts.slice(9,11), mm = ts.slice(11,13), ss = ts.slice(13,15)
        return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
    }

    // **Connections for MOTIONConnector signals**
    Connections {
        target: MOTIONInterface
        function onDirectoryChanged() {
            refreshScans()
        }
    }

    Component.onCompleted: refreshScans()
}