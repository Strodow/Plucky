# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'template_pair_window.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_TemplatePairingWindow(object):
    def setupUi(self, TemplatePairingWindow):
        if not TemplatePairingWindow.objectName():
            TemplatePairingWindow.setObjectName(u"TemplatePairingWindow")
        TemplatePairingWindow.resize(1257, 679)
        self.mainVerticalLayout = QVBoxLayout(TemplatePairingWindow)
        self.mainVerticalLayout.setObjectName(u"mainVerticalLayout")
        self.mainVerticalLayout.setContentsMargins(10, 10, 10, 10)
        self.topBarLayout = QHBoxLayout()
        self.topBarLayout.setObjectName(u"topBarLayout")
        self.pairedTemplateNameComboBox = QComboBox(TemplatePairingWindow)
        self.pairedTemplateNameComboBox.addItem("")
        self.pairedTemplateNameComboBox.setObjectName(u"pairedTemplateNameComboBox")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pairedTemplateNameComboBox.sizePolicy().hasHeightForWidth())
        self.pairedTemplateNameComboBox.setSizePolicy(sizePolicy)

        self.topBarLayout.addWidget(self.pairedTemplateNameComboBox)

        self.addPairedTemplateButton = QPushButton(TemplatePairingWindow)
        self.addPairedTemplateButton.setObjectName(u"addPairedTemplateButton")
        self.addPairedTemplateButton.setMaximumSize(QSize(30, 16777215))

        self.topBarLayout.addWidget(self.addPairedTemplateButton)

        self.removePairedTemplateButton = QPushButton(TemplatePairingWindow)
        self.removePairedTemplateButton.setObjectName(u"removePairedTemplateButton")
        self.removePairedTemplateButton.setMaximumSize(QSize(30, 16777215))

        self.topBarLayout.addWidget(self.removePairedTemplateButton)


        self.mainVerticalLayout.addLayout(self.topBarLayout)

        self.outputsLayout = QHBoxLayout()
        self.outputsLayout.setSpacing(10)
        self.outputsLayout.setObjectName(u"outputsLayout")
        self.output1VerticalLayout = QVBoxLayout()
        self.output1VerticalLayout.setObjectName(u"output1VerticalLayout")
        self.output1Label = QLabel(TemplatePairingWindow)
        self.output1Label.setObjectName(u"output1Label")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.output1Label.setFont(font)
        self.output1Label.setAlignment(Qt.AlignCenter)

        self.output1VerticalLayout.addWidget(self.output1Label)

        self.template1PreviewLabel = QLabel(TemplatePairingWindow)
        self.template1PreviewLabel.setObjectName(u"template1PreviewLabel")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.template1PreviewLabel.sizePolicy().hasHeightForWidth())
        self.template1PreviewLabel.setSizePolicy(sizePolicy1)
        self.template1PreviewLabel.setMinimumSize(QSize(300, 169))
        self.template1PreviewLabel.setFrameShape(QFrame.Box)
        self.template1PreviewLabel.setAlignment(Qt.AlignCenter)

        self.output1VerticalLayout.addWidget(self.template1PreviewLabel)

        self.template1ComboBox = QComboBox(TemplatePairingWindow)
        self.template1ComboBox.addItem("")
        self.template1ComboBox.setObjectName(u"template1ComboBox")

        self.output1VerticalLayout.addWidget(self.template1ComboBox)

        self.output1TextBoxesContainer = QWidget(TemplatePairingWindow)
        self.output1TextBoxesContainer.setObjectName(u"output1TextBoxesContainer")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.output1TextBoxesContainer.sizePolicy().hasHeightForWidth())
        self.output1TextBoxesContainer.setSizePolicy(sizePolicy2)
        self.output1TextBoxesContainer.setVisible(False)

        self.output1VerticalLayout.addWidget(self.output1TextBoxesContainer)


        self.outputsLayout.addLayout(self.output1VerticalLayout)

        self.output2VerticalLayout = QVBoxLayout()
        self.output2VerticalLayout.setObjectName(u"output2VerticalLayout")
        self.output2Label = QLabel(TemplatePairingWindow)
        self.output2Label.setObjectName(u"output2Label")
        self.output2Label.setFont(font)
        self.output2Label.setAlignment(Qt.AlignCenter)

        self.output2VerticalLayout.addWidget(self.output2Label)

        self.template2PreviewLabel = QLabel(TemplatePairingWindow)
        self.template2PreviewLabel.setObjectName(u"template2PreviewLabel")
        sizePolicy1.setHeightForWidth(self.template2PreviewLabel.sizePolicy().hasHeightForWidth())
        self.template2PreviewLabel.setSizePolicy(sizePolicy1)
        self.template2PreviewLabel.setMinimumSize(QSize(300, 169))
        self.template2PreviewLabel.setFrameShape(QFrame.Box)
        self.template2PreviewLabel.setAlignment(Qt.AlignCenter)

        self.output2VerticalLayout.addWidget(self.template2PreviewLabel)

        self.template2ComboBox = QComboBox(TemplatePairingWindow)
        self.template2ComboBox.addItem("")
        self.template2ComboBox.setObjectName(u"template2ComboBox")

        self.output2VerticalLayout.addWidget(self.template2ComboBox)

        self.output2MappingContainer = QWidget(TemplatePairingWindow)
        self.output2MappingContainer.setObjectName(u"output2MappingContainer")
        sizePolicy2.setHeightForWidth(self.output2MappingContainer.sizePolicy().hasHeightForWidth())
        self.output2MappingContainer.setSizePolicy(sizePolicy2)
        self.output2MappingContainer.setVisible(False)

        self.output2VerticalLayout.addWidget(self.output2MappingContainer)


        self.outputsLayout.addLayout(self.output2VerticalLayout)

        self.outputsLayout.setStretch(0, 1)
        self.outputsLayout.setStretch(1, 1)

        self.mainVerticalLayout.addLayout(self.outputsLayout)

        self.bottomButtonsLayout = QHBoxLayout()
        self.bottomButtonsLayout.setObjectName(u"bottomButtonsLayout")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.bottomButtonsLayout.addItem(self.horizontalSpacer)

        self.saveButton = QPushButton(TemplatePairingWindow)
        self.saveButton.setObjectName(u"saveButton")

        self.bottomButtonsLayout.addWidget(self.saveButton)

        self.cancelButton = QPushButton(TemplatePairingWindow)
        self.cancelButton.setObjectName(u"cancelButton")

        self.bottomButtonsLayout.addWidget(self.cancelButton)


        self.mainVerticalLayout.addLayout(self.bottomButtonsLayout)

        self.mainVerticalLayout.setStretch(1, 1)

        self.retranslateUi(TemplatePairingWindow)

        QMetaObject.connectSlotsByName(TemplatePairingWindow)
    # setupUi

    def retranslateUi(self, TemplatePairingWindow):
        TemplatePairingWindow.setWindowTitle(QCoreApplication.translate("TemplatePairingWindow", u"Template Pairing", None))
        self.pairedTemplateNameComboBox.setItemText(0, QCoreApplication.translate("TemplatePairingWindow", u"Paired Template Name", None))

        self.addPairedTemplateButton.setText(QCoreApplication.translate("TemplatePairingWindow", u"+", None))
        self.removePairedTemplateButton.setText(QCoreApplication.translate("TemplatePairingWindow", u"-", None))
        self.output1Label.setText(QCoreApplication.translate("TemplatePairingWindow", u"Output 1", None))
        self.template1PreviewLabel.setText(QCoreApplication.translate("TemplatePairingWindow", u"Template Preview", None))
        self.template1ComboBox.setItemText(0, QCoreApplication.translate("TemplatePairingWindow", u"Template 1", None))

        self.output2Label.setText(QCoreApplication.translate("TemplatePairingWindow", u"Output 2", None))
        self.template2PreviewLabel.setText(QCoreApplication.translate("TemplatePairingWindow", u"Template Preview", None))
        self.template2ComboBox.setItemText(0, QCoreApplication.translate("TemplatePairingWindow", u"Template 2", None))

        self.saveButton.setText(QCoreApplication.translate("TemplatePairingWindow", u"Save", None))
        self.cancelButton.setText(QCoreApplication.translate("TemplatePairingWindow", u"Cancel", None))
    # retranslateUi

