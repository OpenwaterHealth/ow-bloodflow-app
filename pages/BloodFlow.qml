import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0
import OpenMotion 1.0 
import QtQuick.Dialogs as Dialogs


import "../components"
import "./scan"

Rectangle {
    id: bloodFlow
    width: parent.width
    height: parent.height
    color: "#29292B" // Background color for Page 1
    radius: 20
    opacity: 0.95 // Slight transparency for the content area

    // property to store selected directory
    property string defaultDataDir: ""

    // Convert sensorActive[0..7] -> bitmask using mapping: [0,7,1,6,2,5,3,4]
    function maskFromArray(arr) {
        if (!arr || arr.length !== 8) return 0;
        const bitMap = [0, 7, 1, 6, 2, 5, 3, 4];  // index i -> bit number
        var m = 0;
        for (var i = 0; i < 8; i++) {
            if (arr[i]) m |= (1 << bitMap[i]);
        }
        return m;
    }

    // Reactive masks (auto-update when sensorActive arrays change)
    property int leftMask:  maskFromArray(leftSensorView.sensorActive)
    property int rightMask: maskFromArray(rightSensorView.sensorActive)

    // LAYOUT
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 30   // extra left space
        anchors.topMargin: 10
        anchors.rightMargin: 10
        anchors.bottomMargin: 10
        spacing: 10

        // Left Column (Input Panel)
        ColumnLayout {
            spacing: 20

            // Info container
            Rectangle {
                id: patientInfo
                width: 500
                height: 500
                color: "#1E1E20"
                radius: 10
                border.color: "#3E4E6F"
                border.width: 2

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 20

                    // Title
                    Text {
                        text: "Patient Info"
                        font.pixelSize: 20
                        color: "#FFFFFF"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Subject ID Field
                    RowLayout {
                        spacing: 10
                        Layout.fillWidth: true

                        Text {
                            text: "Subject ID:"
                            font.pixelSize: 16
                            color: "#BDC3C7"
                            Layout.alignment: Qt.AlignVCenter
                        }

                        TextField {
                            id: subjectIdField
                            text: MOTIONInterface.subjectId
                            font.pixelSize: 16
                            color: "white"
                            Layout.fillWidth: true
                            background: Rectangle {
                                color: "#2E2E33"
                                radius: 4
                                border.color: "#3E4E6F"
                                border.width: 1
                            }

                            // push UI -> backend when user commits
                            onEditingFinished: {
                                if (text !== MOTIONInterface.subjectId)
                                    MOTIONInterface.subjectId = text
                            }
                        }
                    }

                    // Notes Field (multi-line) - FIXED
                    ColumnLayout {
                        spacing: 6
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        Text {
                            text: "Notes:"
                            font.pixelSize: 16
                            color: "#BDC3C7"
                            horizontalAlignment: Text.AlignLeft
                            Layout.alignment: Qt.AlignLeft
                        }

                        Rectangle {
                            color: "#2E2E33"
                            radius: 6
                            border.color: "#3E4E6F"
                            border.width: 1
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            TextArea {
                                id: notesField
                                anchors.fill: parent
                                anchors.margins: 15
                                font.pixelSize: 14
                                color: "white"
                                wrapMode: Text.Wrap
                                background: null  // Use parent rectangle

                                text: MOTIONInterface.scanNotes   // Initial value from backend
                                onTextChanged: MOTIONInterface.scanNotes = text  // Push updates back
                            }
                        }
                    }
                }
            }

            // Data container
            Rectangle {
                id: dataDirInfo
                width: 500
                height: 160
                color: "#1E1E20"
                radius: 10
                border.color: "#3E4E6F"
                border.width: 2
                enabled: true

                // Default Data Directory Selection
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Text {
                        text: "Default Data Directory:"
                        font.pixelSize: 16
                        color: "#BDC3C7"
                    }

                    TextField {
                        id: directoryField
                        text: MOTIONInterface.directory
                        readOnly: true
                        font.pixelSize: 14
                        color: "white"
                        Layout.fillWidth: true
                        background: Rectangle {
                            color: "#2E2E33"
                            radius: 4
                            border.color: "#3E4E6F"
                            border.width: 1
                        }
                    }
                    
                    Button {
                        id: btnBrowse
                        text: "Browse"
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
                            folderDialog.open()
                        }
                    }

                    Dialogs.FolderDialog {
                        id: folderDialog
                        title: "Select Default Data Directory"
                        currentFolder: Qt.platform.os === "windows"
                            ? "file:///" + MOTIONInterface.directory.replace("\\", "/")
                            : MOTIONInterface.directory

                        onAccepted: {
                            MOTIONInterface.directory = folderDialog.selectedFolder.toString().replace("file:///", "")
                        }
                    }
                }
            }
        }

        // RIGHT COLUMN (Status Panel + Histogram)
        ColumnLayout {
            spacing: 20

            // Sensor Panel
            Rectangle {
                id: sensorSelection
                width: 500
                height: 360
                color: "#1E1E20"
                radius: 10
                border.color: "#3E4E6F"
                border.width: 2
                
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 40

                    // Left Sensor Column
                    ColumnLayout {
                        spacing: 10
                        Layout.alignment: Qt.AlignHCenter

                        SensorView {
                            id: leftSensorView
                            title: "Left Sensor"
                        }

                        ComboBox {
                            id: leftSensorSelector
                            Layout.preferredWidth: 200
                            Layout.preferredHeight: 40
                            model: ["Default","Middle"]

                            onCurrentIndexChanged: {
                                switch (currentIndex) {
                                    case 0: leftSensorView.sensorActive = [false,false,true,true,false,false,true,true]; break;  // 0x5A
                                    case 1: leftSensorView.sensorActive = [false,false,true,true,true,true,false,false]; break;  // 0x66
                                }
                                console.log("Left mask -> 0x" + leftMask.toString(16).toUpperCase());
                            }
                        }
                    }

                    // Right Sensor Column
                    ColumnLayout {
                        spacing: 10
                        Layout.alignment: Qt.AlignHCenter

                        SensorView {
                            id: rightSensorView
                            title: "Right Sensor"
                        }

                        ComboBox {
                            id: rightSensorSelector
                            Layout.preferredWidth: 200
                            Layout.preferredHeight: 40
                            model: ["Default","Middle"]

                            onCurrentIndexChanged: {
                                switch (currentIndex) {
                                    case 0: rightSensorView.sensorActive = [false,false,true,true,false,false,true,true]; break;  // 0x5A
                                    case 1: rightSensorView.sensorActive = [false,false,true,true,true,true,false,false]; break;  // 0x66
                                }                                
                                console.log("Right mask -> 0x" + rightMask.toString(16).toUpperCase());
                            }
                        }
                    }

                    Component.onCompleted: {
                        // Force default selection handlers to run so sensorActive arrays are set
                        leftSensorSelector.currentIndex = 0;
                        rightSensorSelector.currentIndex = 0;
                        console.log("Left mask=0x" + leftMask.toString(16).toUpperCase(),
                                    "Right mask=0x" + rightMask.toString(16).toUpperCase());
                    }
                }
            }

            // Status Panel (Connection Indicators)
            Rectangle {
                id: statusPanel
                width: 500
                height: 120
                color: "#1E1E20"
                radius: 10
                border.color: "#3E4E6F"
                border.width: 2
                

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 20

                    // Right Column: status and indicators
                    ColumnLayout {
                        spacing: 10
                        Layout.preferredWidth: statusPanel.width/2
                        Layout.fillHeight: true
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter

                        RowLayout {
                            spacing: 30
                            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter

                            Text {
                                id: statusText
                                text: "System State: " + (MOTIONInterface.state === 0 ? "Disconnected"
                                                : MOTIONInterface.state === 1 ? "Sensor Connected"
                                                : MOTIONInterface.state === 2 ? "Console Connected"
                                                : MOTIONInterface.state === 3 ? "Ready"
                                                : "Running")
                                font.pixelSize: 16
                                color: "#BDC3C7"
                                horizontalAlignment: Text.AlignRight
                                Layout.alignment: Qt.AlignRight
                            }
                        }

                        RowLayout {
                            spacing: 30
                            Layout.alignment: Qt.AlignHCenter

                            // Sensor Indicator
                            ColumnLayout {
                                spacing: 2
                                Layout.alignment: Qt.AlignHCenter

                                Text {
                                    text: "Sensors"
                                    font.pixelSize: 14
                                    color: "#BDC3C7"
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                RowLayout {
                                    spacing: 4
                                    Layout.alignment: Qt.AlignHCenter

                                    Rectangle {
                                        width: 20; height: 20; radius: 10
                                        color: MOTIONInterface.leftSensorConnected ? "green" : "red"
                                        border.color: "black"; border.width: 1
                                    }

                                    Rectangle {
                                        width: 20; height: 20; radius: 10
                                        color: MOTIONInterface.rightSensorConnected ? "green" : "red"
                                        border.color: "black"; border.width: 1
                                    }
                                }
                            }

                            // Console Indicator
                            ColumnLayout {
                                spacing: 4
                                Layout.alignment: Qt.AlignHCenter

                                Text {
                                    text: "Console"
                                    font.pixelSize: 14
                                    color: "#BDC3C7"
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Rectangle {
                                    width: 20; height: 20; radius: 10
                                    color: MOTIONInterface.consoleConnected ? "green" : "red"
                                    border.color: "black"; border.width: 1
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }

                            // Laser Indicator
                            ColumnLayout {
                                spacing: 4
                                Layout.alignment: Qt.AlignHCenter

                                Text {
                                    text: "Laser"
                                    font.pixelSize: 14
                                    color: "#BDC3C7"
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Rectangle {
                                    width: 20; height: 20; radius: 10
                                    color: MOTIONInterface.triggerState === "ON" ? "green" : "red"
                                    border.color: "black"; border.width: 1
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }

                            // Failure Indicator
                            ColumnLayout {
                                spacing: 4
                                Layout.alignment: Qt.AlignHCenter

                                Text {
                                    text: "Failure"
                                    font.pixelSize: 14
                                    color: "#BDC3C7"
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Rectangle {
                                    width: 20; height: 20; radius: 10
                                    color: MOTIONInterface.safetyFailure ? "red" : "grey"
                                    border.color: "black"; border.width: 1
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }

            // Controls
            Rectangle {
                id: controlPanel
                width: 500
                height: 160
                color: "#1E1E20"
                radius: 10
                border.color: "#3E4E6F"
                border.width: 2

                // public duration value (seconds)
                property int durationSec: 30

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    // === Duration row ===
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        Text {
                            text: "Duration:"
                            color: "#BDC3C7"
                            font.pixelSize: 14
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Slider {
                            id: durationSlider
                            from: 0
                            to: 120
                            stepSize: 1
                            snapMode: Slider.SnapOnRelease
                            value: controlPanel.durationSec
                            Layout.fillWidth: true
                            onValueChanged: controlPanel.durationSec = Math.round(value)
                        }

                        TextField {
                            id: durationEdit
                            text: String(controlPanel.durationSec)
                            inputMethodHints: Qt.ImhDigitsOnly
                            validator: IntValidator { bottom: 0; top: 120 }
                            font.pixelSize: 14
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            Layout.preferredWidth: 64
                            background: Rectangle {
                                color: "#2E2E33"; radius: 4
                                border.color: "#3E4E6F"; border.width: 1
                            }

                            // keep in sync with slider, clamp 0..120
                            onEditingFinished: {
                                let v = parseInt(text);
                                if (isNaN(v)) v = controlPanel.durationSec;
                                v = Math.max(0, Math.min(120, v));
                                controlPanel.durationSec = v;
                                durationSlider.value = v;
                                text = String(v);
                            }
                        }

                        Text {
                            text: "sec"
                            color: "#BDC3C7"
                            font.pixelSize: 14
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }

                    // spacer pushes buttons to bottom
                    Item { Layout.fillHeight: true }

                    // === Bottom buttons ===
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 40

                        Button {
                            id: btnStartScan
                            text: "Start Scan"
                            Layout.preferredWidth: 140
                            Layout.preferredHeight: 60
                            hoverEnabled: enabled
                            enabled: MOTIONInterface.consoleConnected && (MOTIONInterface.leftSensorConnected || MOTIONInterface.rightSensorConnected)

                            contentItem: Text {
                                text: parent.text
                                font.pixelSize: 16
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
                                console.log("Start Scan", controlPanel.durationSec, "sec");
                                // start scan
                                // MOTIONInterface.startTrigger() 
                                //scanDialog.message = "Scanning"
                                //scanDialog.open()
                                
                                scanDialog.message = "Scanning…";
                                scanDialog.stageText = "Preparing…";
                                scanDialog.progress = 1;
                                scanDialog.open();
                                scanRunner.start();
                            }
                        }
                        
                    }
                }
            }


        }

    }
    
    // **Connections for MOTIONConnector signals**
    Connections {
        target: MOTIONInterface

        function onSignalConnected(descriptor, port) {
            console.log(descriptor + " connected on " + port);
            statusText.text = "Connected: " + descriptor + " on " + port;

            if ((descriptor || "").toUpperCase() === "CONSOLE") {
                
            }
        }

        function onSignalDisconnected(descriptor, port) {
            console.log(descriptor + " disconnected from " + port);
            statusText.text = "Disconnected: " + descriptor + " from " + port;
            

            if ((descriptor || "").toUpperCase() === "CONSOLE") {
            }
        }

        function onSignalDataReceived(descriptor, message) {
            console.log("Data from " + descriptor + ": " + message);
        }
        
        function onConnectionStatusChanged() {          
            if (MOTIONInterface.leftSensorConnected) {

            }   
            if (MOTIONInterface.consoleConnected) {
                
            }            
        }
        
        function onLaserStateChanged() {          
            if (MOTIONInterface.consoleConnected) {
            }            
        }
        
        function onSafetyFailureStateChanged() {          
            if (MOTIONInterface.consoleConnected) {
            }            
        }

    }

    Component.onDestruction: {
        console.log("Closing UI, clearing MOTIONInterface...");
    }

    ScanProgressDialog {
        id: scanDialog
        onCancelRequested: {
            if (scanDialog.done) {
                // After success or error review, Close should just dismiss
                scanDialog.close()
            } else {
                // While running, Cancel should actually cancel the scan
                scanRunner.cancel()
            }
        }
    }

    ScanRunner {
        id: scanRunner
        // connector: use the globally-exposed connector if it exists, else null
        connector: MOTIONInterface

        // inputs with safe fallbacks
        leftMask: bloodFlow.leftMask
        rightMask: bloodFlow.rightMask
        cameraMask: bloodFlow.leftMask // need to issue masks for each side currently just takes one mask
        durationSec: controlPanel.durationSec
        subjectId: subjectIdField.text
        dataDir: directoryField.text
        disableLaser: false                        // add a checkbox later 
        laserOn: true
        laserPower: 50
        triggerConfig: (typeof appTriggerConfig !== "undefined") ? appTriggerConfig : ({
            "TriggerFrequencyHz": 40,
            "TriggerPulseWidthUsec": 500,
            "LaserPulseDelayUsec": 100,
            "LaserPulseWidthUsec": 500,
            "LaserPulseSkipInterval": 600,
            "EnableSyncOut": true,
            "EnableTaTrigger": true
        })


        onStageUpdate: function(txt) {
            if (!scanDialog.visible) scanDialog.open();
            scanDialog.stageText = txt;
        }
        onProgressUpdate: function(pct) {
            if (!scanDialog.visible) scanDialog.open();
            scanDialog.progress = pct;
        }
        onMessageOut: function(line) { scanDialog.appendLog(line) }
        onScanFinished: function(ok, err, left, right) {

            if (err === "Canceled") {
                // Cancel should CLOSE the dialog
                scanDialog.close()
                return
            }

            if (!ok) {
                scanDialog.appendLog("ERROR: " + err);
                scanDialog.stageText = "Error during capture";
                // keep it open so you can read the error
                scanDialog.done = true
                return;
            }

            // Success: keep open if you want, but make the button say Close
            scanDialog.stageText = "Capture complete"
            scanDialog.progress = 100
            scanDialog.done = true
            // scanDialog.close();
        }
    }
}
