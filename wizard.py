#!/usr/bin/env python3
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2020, Jorge Martin'

import sys
from PySide2.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout,
    QLabel, QProgressBar, QPlainTextEdit, QFileDialog,
    QRadioButton, QComboBox, QLineEdit, QPushButton, QGridLayout, QInputDialog)
from PySide2.QtCore import (QThread, QObject, Signal, Slot)
from PySide2.QtGui import QTextCursor
import subprocess
import re
import json


class AcquisitionWizard(QWizard):
    def __init__(self, parent=None):
        super(AcquisitionWizard, self).__init__(parent)

        self.addPage(InfoPage())
        self.addPage(SelectionPage())
        self.addPage(StatusPage())
        self.addPage(ConclusionPage())

        self.setWindowTitle("Acquisition Wizard")


class InfoPage(QWizardPage):
    def __init__(self, parent=None):
        super(InfoPage, self).__init__(parent)

        label = QLabel("This wizard will generate a skeleton C++ class "
            "definition, including a few functions. You simply need to "
            "specify the class name and set a few options to produce a "
            "header file and an implementation file for your new C++ "
            "class.")
        label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)


class SelectionPage(QWizardPage):

    def __init__(self, parent=None):
        super(SelectionPage, self).__init__(parent)
        label1 = QLabel("Input:  ")
        label2 = QLabel("Output: ")
        self.combo = QComboBox()
        self.updatePaths()
        self.registerField("input*", self.combo, "currentText", "currentTextChanged()")
        self.line = QLineEdit()
        self.registerField("output*", self.line)
        button1 = QPushButton("Update")
        button1.clicked.connect(self.updatePaths)
        button2 = QPushButton("Select")
        button2.clicked.connect(self.openDialog)
        grid_layout = QGridLayout()
        grid_layout.addWidget(label1, 0, 0)
        grid_layout.addWidget(label2, 1, 0)
        grid_layout.addWidget(self.combo, 0, 1)
        grid_layout.addWidget(self.line, 1, 1)
        grid_layout.addWidget(button1, 0, 2)
        grid_layout.addWidget(button2, 1, 2)

        self.setLayout(grid_layout)

    def initializePage(self):
        self.setButtonText(QWizard.NextButton, "Acquire")

    def list_paths(self):
        process = subprocess.run(["/bin/lsblk", "--json", "-o", "PATH"], capture_output=True, text=True)
        units = json.loads(process.stdout)
        return [blockdevice['path'] for blockdevice in units['blockdevices']]

    def updatePaths(self):
        self.combo.clear()
        self.combo.addItem("None")
        for path in self.list_paths():
            self.combo.addItem(path)

    def openDialog(self):
        filename, _ = QFileDialog.getOpenFileName(self)
        self.line.insert(filename)

    def validatePage(self):
        # Hay que recorrer una rray de hijos y ver que ninguno esté activo
        return self.combo.currentIndex() > 0 and len(self.line.text()) > 0

class AcquireWorker(QObject):

    progress = Signal(int)
    log = Signal(str)

    def __init__(self, input_filename, output_filename):
        super(AcquireWorker, self).__init__()
        self.input_filename = input_filename
        self.output_filename = output_filename


    @Slot()
    def start(self):
        process = subprocess.Popen(["/usr/bin/ewfacquire", "-u", "-l", self.output_filename + ".log", "-t", self.output_filename, self.input_filename],
                                           stdout=subprocess.PIPE, text=True)
        regex = re.compile('Status: at (\d+)%')
        regex2 = re.compile('Acquiry completed at:')
        for line in iter(process.stdout.readline, ''):
            self.log.emit(line)
            match = regex.search(line)
            if match:
                self.progress.emit(int(match.group(1)))
            match2 = regex2.search(line)
            if match2:
                self.progress.emit(100)


class StatusPage(QWizardPage):

    def __init__(self, parent=None):
        super(StatusPage, self).__init__(parent)
        self.text_pane = QPlainTextEdit()
        self.text_pane.setReadOnly(True)
        self.progress_bar = QProgressBar()
        layout = QVBoxLayout()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.text_pane)
        self.setLayout(layout)

    def initializePage(self):
        input_filename = self.field("input")
        output_filename = self.field("output")
        self.thread = QThread()
        self.worker = AcquireWorker(input_filename, output_filename)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.on_log)
        self.thread.started.connect(self.worker.start)
        self.worker.moveToThread(self.thread)
        self.thread.start()

    def on_progress(self, progress):
        self.progress_bar.setValue(progress)
        self.completeChanged.emit()

    def on_log(self, line):
        self.text_pane.insertPlainText(line)
        self.text_pane.moveCursor(QTextCursor.End)

    def isComplete(self):
        return self.progress_bar.value() == 100

class ConclusionPage(QWizardPage):
    def __init__(self, parent=None):
        super(ConclusionPage, self).__init__(parent)

        label = QLabel("This wizard will generate a skeleton C++ class "
            "definition, including a few functions. You simply need to "
            "specify the class name and set a few options to produce a "
            "header file and an implementation file for your new C++ "
            "class.")
        label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication([])
    wizard = AcquisitionWizard()
    wizard.show()
    # ...
    sys.exit(app.exec_())