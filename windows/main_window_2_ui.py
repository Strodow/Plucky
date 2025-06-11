# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QMenuBar, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QVBoxLayout, QWidget)

from main_window_2.py import PreviewOutputWidget

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 720)
        self.actionNew_Presentation = QAction(MainWindow)
        self.actionNew_Presentation.setObjectName(u"actionNew_Presentation")
        self.actionLoad_Presentation = QAction(MainWindow)
        self.actionLoad_Presentation.setObjectName(u"actionLoad_Presentation")
        self.actionSave = QAction(MainWindow)
        self.actionSave.setObjectName(u"actionSave")
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionStart_DeckLink_Output = QAction(MainWindow)
        self.actionStart_DeckLink_Output.setObjectName(u"actionStart_DeckLink_Output")
        self.actionStart_DeckLink_Output.setCheckable(True)
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionUndo = QAction(MainWindow)
        self.actionUndo.setObjectName(u"actionUndo")
        self.actionRedo = QAction(MainWindow)
        self.actionRedo.setObjectName(u"actionRedo")
        self.central_widget = QWidget(MainWindow)
        self.central_widget.setObjectName(u"central_widget")
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setObjectName(u"main_layout")
        self.splitter = QSplitter(self.central_widget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.left_panel = QWidget(self.splitter)
        self.left_panel.setObjectName(u"left_panel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setObjectName(u"left_layout")
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setObjectName(u"controls_layout")
        self.undo_button = QPushButton(self.left_panel)
        self.undo_button.setObjectName(u"undo_button")

        self.controls_layout.addWidget(self.undo_button)

        self.redo_button = QPushButton(self.left_panel)
        self.redo_button.setObjectName(u"redo_button")

        self.controls_layout.addWidget(self.redo_button)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controls_layout.addItem(self.horizontalSpacer)

        self.clear_button = QPushButton(self.left_panel)
        self.clear_button.setObjectName(u"clear_button")

        self.controls_layout.addWidget(self.clear_button)

        self.go_live_button = QPushButton(self.left_panel)
        self.go_live_button.setObjectName(u"go_live_button")

        self.controls_layout.addWidget(self.go_live_button)


        self.left_layout.addLayout(self.controls_layout)

        self.label_slides = QLabel(self.left_panel)
        self.label_slides.setObjectName(u"label_slides")

        self.left_layout.addWidget(self.label_slides)

        self.scroll_area = QScrollArea(self.left_panel)
        self.scroll_area.setObjectName(u"scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.slide_buttons_widget = QWidget()
        self.slide_buttons_widget.setObjectName(u"slide_buttons_widget")
        self.slide_buttons_widget.setGeometry(QRect(0, 0, 430, 587))
        self.slide_buttons_layout = QVBoxLayout(self.slide_buttons_widget)
        self.slide_buttons_layout.setObjectName(u"slide_buttons_layout")
        self.slide_buttons_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.slide_buttons_widget)

        self.left_layout.addWidget(self.scroll_area)

        self.splitter.addWidget(self.left_panel)
        self.right_panel = QWidget(self.splitter)
        self.right_panel.setObjectName(u"right_panel")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setObjectName(u"right_layout")
        self.label_preview = QLabel(self.right_panel)
        self.label_preview.setObjectName(u"label_preview")

        self.right_layout.addWidget(self.label_preview)

        self.preview_widget = PreviewOutputWidget(self.right_panel)
        self.preview_widget.setObjectName(u"preview_widget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.preview_widget.sizePolicy().hasHeightForWidth())
        self.preview_widget.setSizePolicy(sizePolicy)
        self.preview_widget.setMinimumSize(QSize(240, 135))

        self.right_layout.addWidget(self.preview_widget)

        self.label_program = QLabel(self.right_panel)
        self.label_program.setObjectName(u"label_program")

        self.right_layout.addWidget(self.label_program)

        self.program_output_label = QLabel(self.right_panel)
        self.program_output_label.setObjectName(u"program_output_label")
        sizePolicy.setHeightForWidth(self.program_output_label.sizePolicy().hasHeightForWidth())
        self.program_output_label.setSizePolicy(sizePolicy)
        self.program_output_label.setAlignment(Qt.AlignCenter)

        self.right_layout.addWidget(self.program_output_label)

        self.splitter.addWidget(self.right_panel)

        self.main_layout.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.central_widget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1280, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuEdit = QMenu(self.menubar)
        self.menuEdit.setObjectName(u"menuEdit")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menuFile.addAction(self.actionNew_Presentation)
        self.menuFile.addAction(self.actionLoad_Presentation)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionStart_DeckLink_Output)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuEdit.addAction(self.actionUndo)
        self.menuEdit.addAction(self.actionRedo)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Plucky Presentation (Redesigned)", None))
        self.actionNew_Presentation.setText(QCoreApplication.translate("MainWindow", u"New Presentation", None))
        self.actionLoad_Presentation.setText(QCoreApplication.translate("MainWindow", u"Load Presentation...", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Save As...", None))
        self.actionStart_DeckLink_Output.setText(QCoreApplication.translate("MainWindow", u"Start DeckLink Output", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.actionUndo.setText(QCoreApplication.translate("MainWindow", u"Undo", None))
#if QT_CONFIG(shortcut)
        self.actionUndo.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Z", None))
#endif // QT_CONFIG(shortcut)
        self.actionRedo.setText(QCoreApplication.translate("MainWindow", u"Redo", None))
#if QT_CONFIG(shortcut)
        self.actionRedo.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Y", None))
#endif // QT_CONFIG(shortcut)
        self.undo_button.setText(QCoreApplication.translate("MainWindow", u"Undo", None))
        self.redo_button.setText(QCoreApplication.translate("MainWindow", u"Redo", None))
        self.clear_button.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.go_live_button.setStyleSheet(QCoreApplication.translate("MainWindow", u"background-color: #C84630; color: white; font-weight: bold;", None))
        self.go_live_button.setText(QCoreApplication.translate("MainWindow", u"TAKE", None))
        self.label_slides.setText(QCoreApplication.translate("MainWindow", u"Slides:", None))
        self.label_preview.setText(QCoreApplication.translate("MainWindow", u"Preview:", None))
        self.label_program.setText(QCoreApplication.translate("MainWindow", u"Program:", None))
        self.program_output_label.setStyleSheet(QCoreApplication.translate("MainWindow", u"background-color: black; color: gray;", None))
        self.program_output_label.setText(QCoreApplication.translate("MainWindow", u"Program Output", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuEdit.setTitle(QCoreApplication.translate("MainWindow", u"Edit", None))
    # retranslateUi

