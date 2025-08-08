# OpenMOTION Test Application

Python example UI for OPEN Motion used for Hardware Testing and Basic Usage

![App Image](docs/app_image.png)

## Installation

### Prerequisites
- **Python 3.9 or later**: Make sure you have Python 3.9 or later installed on your system. You can download it from the [official Python website](https://www.python.org/downloads/).

### Steps to Set Up the Project
1. **Install OpenLIFU Python**
   ```bash
   https://github.com/OpenwaterHealth/OpenMOTION-Pylib
   cd OpenMOTION-Pylib
   pip install -r requirements.txt
   ```

2. **Clone the repository and Install Required Packages**:
   ```bash
   git clone https://github.com/OpenwaterHealth/OpenMOTION-TestAPP.git
   cd OpenMOTION-TestAPP
   pip install -r requirements.txt
   ```

3. **Install libusb for your system**
   requires libusb to be installed, for windows install the dll to c:\windows\system32, download the correct dll from github

   ```
   https://github.com/libusb/libusb/releases
   ```

3. **Run application**
   requires OpenMOTION-Pylib to be installed or referenced prior to running main.py

   ```bash
   cd OpenMOTION-TestAPP
   python main.py
   ```