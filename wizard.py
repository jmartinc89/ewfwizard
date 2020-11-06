#!/usr/bin/env python3
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2020, Jorge Martin'

import sys
from PySide2.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout,
    QLabel, QProgressBar, QPlainTextEdit, QFileDialog, QSpinBox, QTextEdit,
    QRadioButton, QComboBox, QLineEdit, QPushButton, QGridLayout, QInputDialog)
from PySide2.QtCore import (QThread, QObject, Signal, Slot)
from PySide2.QtGui import QTextCursor
from subprocess import Popen, PIPE, run
from pathlib import PurePath
import re
import json


class AcquisitionWizard(QWizard):
    def __init__(self, parent=None):
        super(AcquisitionWizard, self).__init__(parent)

        self.addPage(InfoPage())
        self.addPage(CasePage())
        self.addPage(SelectionPage())
        self.addPage(StatusPage())
        self.addPage(ConclusionPage())

        self.setWindowTitle("Acquisition Wizard")


class InfoPage(QWizardPage):
    def __init__(self, parent=None):
        super(InfoPage, self).__init__(parent)

        label = QLabel("This wizard creates a forensic image with ewfadquire")
        label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)

class CasePage(QWizardPage):
    def __init__(self, parent=None):
        super(CasePage, self).__init__(parent)
        label1 = QLabel("Case number:     ")
        label2 = QLabel("Description:     ")
        label3 = QLabel("Evidence number: ")
        label4 = QLabel("Examiner name:   ")
        label5 = QLabel("Notes:           ")
        label6 = QLabel("Media type:      ")
        label7 = QLabel("Media flags:     ")
        spinb1 = QSpinBox(self)
        self.registerField("casenum", spinb1)
        eline2 = QLineEdit(self)
        self.registerField("desc", eline2)
        spinb3 = QSpinBox(self)
        self.registerField("evidencenum", spinb3)
        eline4 = QLineEdit(self)
        self.registerField("examiner", eline4)
        etext5 = QTextEdit(self)
        self.registerField("notes", etext5, "plainText", "textChanged()")
        combo6 = QComboBox(self)
        combo6.insertItem(0, "fixed")
        combo6.insertItem(1, "removable")
        combo6.insertItem(2, "optical")
        combo6.insertItem(3, "memory")
        self.registerField("mtype", combo6, "currentText", "currentTextChanged()")
        combo7 = QComboBox(self)
        combo7.insertItem(0, "physical")
        combo7.insertItem(1, "logical")
        self.registerField("mflags", combo7, "currentText", "currentTextChanged()")
        mainLayout = QGridLayout()
        mainLayout.addWidget(label1, 0, 0);
        mainLayout.addWidget(spinb1, 0, 1);
        mainLayout.addWidget(label2, 1, 0);
        mainLayout.addWidget(eline2, 1, 1);
        mainLayout.addWidget(label3, 2, 0);
        mainLayout.addWidget(spinb3, 2, 1);
        mainLayout.addWidget(label4, 3, 0);
        mainLayout.addWidget(eline4, 3, 1);
        mainLayout.addWidget(label5, 4, 0);
        mainLayout.addWidget(etext5, 4, 1);
        mainLayout.addWidget(label6, 5, 0);
        mainLayout.addWidget(combo6, 5, 1);
        mainLayout.addWidget(label7, 6, 0);
        mainLayout.addWidget(combo7, 6, 1);
        self.setLayout(mainLayout)


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
        process = run(["/bin/lsblk", "--json", "-o", "PATH"], capture_output=True, text=True)
        units = json.loads(process.stdout)
        return [blockdevice['path'] for blockdevice in units['blockdevices']]

    def updatePaths(self):
        self.combo.clear()
        self.combo.addItem("None")
        for path in self.list_paths():
            self.combo.addItem(path)

    def openDialog(self):
        fileDialog = QFileDialog(self)
        fileDialog.setNameFilter("Encase Witness Compression Format (*.E??)")
        fileDialog.setAcceptMode(QFileDialog.AcceptSave)
        fileDialog.setLabelText(QFileDialog.LookIn, "Save forensic image")
        fileDialog.setOption(QFileDialog.ReadOnly, True)
        if fileDialog.exec_():
            filepath = PurePath(fileDialog.selectedFiles()[0])
            if filepath.suffix:
                filepath = filepath.with_suffix('')
            self.line.insert(str(filepath))

    def validatePage(self):
        # Hay que recorrer una rray de hijos y ver que ninguno esté activo
        return self.combo.currentIndex() > 0 and len(self.line.text()) > 0

class AcquireWorker(QObject):

    progress = Signal(int)
    log = Signal(str)

    def __init__(self, input_filename, output_filename, case_number, description, evidence_number,
                 examiner, notes, media_type, media_flags):
        super(AcquireWorker, self).__init__()
        self.input_filename = input_filename
        self.output_filename = output_filename
        self.digest_type = "sha1"
        self.case_number = str(case_number)
        self.description = '\"' + description + '\"'
        self.evidence_number = str(evidence_number)
        self.examiner = '\"' + examiner + '\"'
        self.notes = '\"' + notes + '\"'
        self.media_type = media_type
        self.media_flags = media_flags


    @Slot()
    def start(self):
        log_path = PurePath(self.output_filename).with_suffix('.log')
        log_file = open(str(log_path), 'w', encoding='utf-8')
        log_file.write(f'Case number:\t{self.case_number}\n')
        log_file.write(f'Description:\t{self.description}\n')
        log_file.write(f'Examiner name:\t{self.evidence_number}\n')
        log_file.write(f'Evidence number:\t{self.examiner}\n')
        log_file.write(f'Notes:\t{self.notes}\n')
        log_file.write(f'Media type:\t{self.media_type}\n')
        log_file.write(f'Media flags:\t{self.media_flags}\n')


        command = ['/usr/bin/ewfacquire', '-u', '-C', self.case_number, '-D', self.description,
                   '-E', self.evidence_number, '-e', self.examiner, '-N', self.notes,
                   '-m', self.media_type, '-M', self.media_flags, '-d', self.digest_type,
                   '-t', self.output_filename, self.input_filename]

        self.process = Popen(command,stdout=PIPE, text=True)
        regex = re.compile('Status: at (\d+)%')
        regex2 = re.compile('ewfacquire: SUCCESS')

        for line in iter(self.process.stdout.readline, ''):
            log_file.write(line)
            self.log.emit(line)
            match = regex.search(line)
            if match:
                self.progress.emit(int(match.group(1)))
            match2 = regex2.search(line)
            if match2:
                log_file.flush()
                log_file.close()
                self.process.kill()
                self.progress.emit(100)
                break





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
        self.thread = QThread()
        self.worker = AcquireWorker(self.field("input"), self.field("output"), self.field('casenum'),
            self.field('desc'), self.field('evidencenum'), self.field('examiner'), self.field('notes'),
            self.field('mtype'), self.field('mflags'))
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.on_log)
        self.thread.started.connect(self.worker.start)
        self.thread.finished.connect(self.worker.deleteLater)
        self.worker.moveToThread(self.thread)
        self.thread.start()

    def cleanupPage(self):
        self.worker.process.kill()
        self.thread.terminate()
        self.thread.wait()

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

        label = QLabel("The forensic image was created.")
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
