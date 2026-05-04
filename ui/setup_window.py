"""
ALEX -- Installation Wizard
A standard Windows-style installer for first-time configuration.
Handles directory creation and API key registration.
"""

import sys
import os
from PyQt6.QtWidgets import (QWizard, QWizardPage, QLabel, QVBoxLayout, 
                             QLineEdit, QVBoxLayout, QApplication, QCheckBox)
from PyQt6.QtCore import Qt

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to the ALEX Setup Wizard")
        layout = QVBoxLayout()
        label = QLabel("This wizard will guide you through the initial configuration of ALEX — your AI Execution Assistant.\n\n"
                       "We will set up the local database folders and register your API keys.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

class FolderPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("System Initialization")
        self.setSubTitle("Creating necessary local directories...")
        
        layout = QVBoxLayout()
        self.status_label = QLabel("Ready to initialize...")
        layout.addWidget(self.status_label)
        
        self.check = QCheckBox("I understand that ALEX will store conversation data locally in a 'memory' folder.")
        layout.addWidget(self.check)
        self.registerField("agreement*", self.check) # Required to proceed
        
        self.setLayout(layout)

    def validatePage(self):
        # This runs when they click 'Next'
        try:
            # We create the folders here
            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
            for folder in ["memory", "logs"]:
                path = os.path.join(base_dir, folder)
                if not os.path.exists(path):
                    os.makedirs(path)
            self.status_label.setText("Success: Local folders created.")
            return True
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            return False

class APIKeyPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("API Configuration")
        self.setSubTitle("Please enter your Groq API keys. These are stored locally on your device.")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Primary API Key:"))
        self.key1 = QLineEdit()
        self.key1.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key1)
        self.registerField("groq_key1*", self.key1)

        layout.addWidget(QLabel("Fallback API Key (Required):"))
        self.key2 = QLineEdit()
        self.key2.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key2)
        self.registerField("groq_key2*", self.key2)

        layout.addStretch()
        layout.addWidget(QLabel("<i>Note: ALEX uses a tiered failover system. If the primary key hits a rate limit, it switches to the fallback.</i>"))
        
        self.setLayout(layout)

class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Complete")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("ALEX has been successfully initialized.\n\n"
                                "Click 'Finish' to launch the assistant. You can activate ALEX at any time using the hotkey (CTRL+SPACE)."))
        self.setLayout(layout)

class AlexInstaller(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALEX Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setFixedSize(500, 400)

        # Add pages
        self.addPage(WelcomePage())
        self.addPage(FolderPage())
        self.addPage(APIKeyPage())
        self.addPage(FinishPage())

        self.setButtonText(QWizard.WizardButton.FinishButton, "Launch ALEX")

    def accept(self):
        # This runs when they click 'Finish'
        k1 = self.field("groq_key1")
        k2 = self.field("groq_key2")

        # Save to .env
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        env_path = os.path.join(base_dir, ".env")
        
        with open(env_path, "w") as f:
            f.write(f"GROQ_API_KEY={k1}\n")
            f.write(f"GROQ_API_KEY_2={k2}\n")
            f.write("LOG_LEVEL=INFO\n")

        super().accept()

def run_setup():
    app = QApplication.instance() or QApplication(sys.argv)
    # Use standard system style for a 'normal' look
    app.setStyle("Fusion") 
    
    wizard = AlexInstaller()
    wizard.show()
    app.exec()
    
    # Return true if setup was finished
    base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
    return os.path.exists(os.path.join(base_dir, ".env"))
