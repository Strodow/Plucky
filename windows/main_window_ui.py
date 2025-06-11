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
from PySide6.QtWidgets import (QApplication, QDockWidget, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMenuBar, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSpinBox,
    QSplitter, QStatusBar, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(900, 700)
        self.actionNew = QAction(MainWindow)
        self.actionNew.setObjectName(u"actionNew")
        self.actionLoad = QAction(MainWindow)
        self.actionLoad.setObjectName(u"actionLoad")
        self.actionSave = QAction(MainWindow)
        self.actionSave.setObjectName(u"actionSave")
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.actionUndo = QAction(MainWindow)
        self.actionUndo.setObjectName(u"actionUndo")
        self.actionRedo = QAction(MainWindow)
        self.actionRedo.setObjectName(u"actionRedo")
        self.actionGo_Live = QAction(MainWindow)
        self.actionGo_Live.setObjectName(u"actionGo_Live")
        self.actionAdd_New_Section = QAction(MainWindow)
        self.actionAdd_New_Section.setObjectName(u"actionAdd_New_Section")
        self.actionSection_Manager_PMenu = QAction(MainWindow)
        self.actionSection_Manager_PMenu.setObjectName(u"actionSection_Manager_PMenu")
        self.actionSection_Manager_VMenu = QAction(MainWindow)
        self.actionSection_Manager_VMenu.setObjectName(u"actionSection_Manager_VMenu")
        self.actionOpen_Settings = QAction(MainWindow)
        self.actionOpen_Settings.setObjectName(u"actionOpen_Settings")
        self.actionResource_Manager = QAction(MainWindow)
        self.actionResource_Manager.setObjectName(u"actionResource_Manager")
        self.actionEnable_Hover_Debug = QAction(MainWindow)
        self.actionEnable_Hover_Debug.setObjectName(u"actionEnable_Hover_Debug")
        self.actionEnable_Hover_Debug.setCheckable(True)
        self.actionToggle_Dirty_State_Debug = QAction(MainWindow)
        self.actionToggle_Dirty_State_Debug.setObjectName(u"actionToggle_Dirty_State_Debug")
        self.actionShow_Environment_Variables = QAction(MainWindow)
        self.actionShow_Environment_Variables.setObjectName(u"actionShow_Environment_Variables")
        self.actionRun_Compositing_Test = QAction(MainWindow)
        self.actionRun_Compositing_Test.setObjectName(u"actionRun_Compositing_Test")
        self.central_widget = QWidget(MainWindow)
        self.central_widget.setObjectName(u"central_widget")
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setObjectName(u"main_layout")
        self.splitter = QSplitter(self.central_widget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.left_panel_widget = QWidget(self.splitter)
        self.left_panel_widget.setObjectName(u"left_panel_widget")
        self.left_layout = QVBoxLayout(self.left_panel_widget)
        self.left_layout.setObjectName(u"left_layout")
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.file_ops_layout = QHBoxLayout()
        self.file_ops_layout.setObjectName(u"file_ops_layout")
        self.label_preview_size = QLabel(self.left_panel_widget)
        self.label_preview_size.setObjectName(u"label_preview_size")

        self.file_ops_layout.addWidget(self.label_preview_size)

        self.preview_size_spinbox = QSpinBox(self.left_panel_widget)
        self.preview_size_spinbox.setObjectName(u"preview_size_spinbox")
        self.preview_size_spinbox.setMinimum(1)
        self.preview_size_spinbox.setMaximum(4)

        self.file_ops_layout.addWidget(self.preview_size_spinbox)

        self.horizontalSpacer_1 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.file_ops_layout.addItem(self.horizontalSpacer_1)

        self.dirty_indicator_label = QLabel(self.left_panel_widget)
        self.dirty_indicator_label.setObjectName(u"dirty_indicator_label")
        self.dirty_indicator_label.setMinimumSize(QSize(16, 16))
        self.dirty_indicator_label.setMaximumSize(QSize(16, 16))

        self.file_ops_layout.addWidget(self.dirty_indicator_label)

        self.edit_template_button = QPushButton(self.left_panel_widget)
        self.edit_template_button.setObjectName(u"edit_template_button")

        self.file_ops_layout.addWidget(self.edit_template_button)

        self.undo_button = QPushButton(self.left_panel_widget)
        self.undo_button.setObjectName(u"undo_button")

        self.file_ops_layout.addWidget(self.undo_button)

        self.redo_button = QPushButton(self.left_panel_widget)
        self.redo_button.setObjectName(u"redo_button")

        self.file_ops_layout.addWidget(self.redo_button)

        self.horizontalSpacer_stretch = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.file_ops_layout.addItem(self.horizontalSpacer_stretch)

        self.decklink_keyer_control_layout = QVBoxLayout()
        self.decklink_keyer_control_layout.setObjectName(u"decklink_keyer_control_layout")
        self.label_dl_output = QLabel(self.left_panel_widget)
        self.label_dl_output.setObjectName(u"label_dl_output")
        self.label_dl_output.setAlignment(Qt.AlignCenter)

        self.decklink_keyer_control_layout.addWidget(self.label_dl_output)

        self.decklink_output_toggle_button = QPushButton(self.left_panel_widget)
        self.decklink_output_toggle_button.setObjectName(u"decklink_output_toggle_button")
        self.decklink_output_toggle_button.setMinimumSize(QSize(24, 24))
        self.decklink_output_toggle_button.setMaximumSize(QSize(24, 24))
        self.decklink_output_toggle_button.setCheckable(True)

        self.decklink_keyer_control_layout.addWidget(self.decklink_output_toggle_button)


        self.file_ops_layout.addLayout(self.decklink_keyer_control_layout)

        self.horizontalSpacer_2 = QSpacerItem(5, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.file_ops_layout.addItem(self.horizontalSpacer_2)

        self.output_control_layout = QVBoxLayout()
        self.output_control_layout.setObjectName(u"output_control_layout")
        self.label_output = QLabel(self.left_panel_widget)
        self.label_output.setObjectName(u"label_output")
        self.label_output.setAlignment(Qt.AlignCenter)

        self.output_control_layout.addWidget(self.label_output)

        self.go_live_button = QPushButton(self.left_panel_widget)
        self.go_live_button.setObjectName(u"go_live_button")
        self.go_live_button.setMinimumSize(QSize(24, 24))
        self.go_live_button.setMaximumSize(QSize(24, 24))
        self.go_live_button.setCheckable(True)

        self.output_control_layout.addWidget(self.go_live_button)


        self.file_ops_layout.addLayout(self.output_control_layout)


        self.left_layout.addLayout(self.file_ops_layout)

        self.verticalSpacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.left_layout.addItem(self.verticalSpacer)

        self.label_slides = QLabel(self.left_panel_widget)
        self.label_slides.setObjectName(u"label_slides")

        self.left_layout.addWidget(self.label_slides)

        self.scroll_area = QScrollArea(self.left_panel_widget)
        self.scroll_area.setObjectName(u"scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.slide_buttons_widget = QWidget()
        self.slide_buttons_widget.setObjectName(u"slide_buttons_widget")
        self.slide_buttons_widget.setGeometry(QRect(0, 0, 346, 596))
        self.slide_buttons_layout = QVBoxLayout(self.slide_buttons_widget)
        self.slide_buttons_layout.setSpacing(0)
        self.slide_buttons_layout.setObjectName(u"slide_buttons_layout")
        self.slide_buttons_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.slide_buttons_widget)

        self.left_layout.addWidget(self.scroll_area)

        self.splitter.addWidget(self.left_panel_widget)

        self.main_layout.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.central_widget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 900, 22))
        self.menu_File = QMenu(self.menubar)
        self.menu_File.setObjectName(u"menu_File")
        self.recent_files_menu = QMenu(self.menu_File)
        self.recent_files_menu.setObjectName(u"recent_files_menu")
        self.menu_Edit = QMenu(self.menubar)
        self.menu_Edit.setObjectName(u"menu_Edit")
        self.menu_Presentation = QMenu(self.menubar)
        self.menu_Presentation.setObjectName(u"menu_Presentation")
        self.menu_View = QMenu(self.menubar)
        self.menu_View.setObjectName(u"menu_View")
        self.menu_Settings = QMenu(self.menubar)
        self.menu_Settings.setObjectName(u"menu_Settings")
        self.menu_Tools = QMenu(self.menubar)
        self.menu_Tools.setObjectName(u"menu_Tools")
        self.menu_Developer = QMenu(self.menubar)
        self.menu_Developer.setObjectName(u"menu_Developer")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.SectionManagementDock = QDockWidget(MainWindow)
        self.SectionManagementDock.setObjectName(u"SectionManagementDock")
        self.SectionManagementDock1 = QWidget()
        self.SectionManagementDock1.setObjectName(u"SectionManagementDock1")
        self.SectionManagementDock.setWidget(self.SectionManagementDock1)
        MainWindow.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.SectionManagementDock)
        self.media_pool_panel = QDockWidget(MainWindow)
        self.media_pool_panel.setObjectName(u"media_pool_panel")
        self.media_pool_panel1 = QWidget()
        self.media_pool_panel1.setObjectName(u"media_pool_panel1")
        self.media_pool_panel.setWidget(self.media_pool_panel1)
        MainWindow.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.media_pool_panel)

        self.menubar.addAction(self.menu_File.menuAction())
        self.menubar.addAction(self.menu_Edit.menuAction())
        self.menubar.addAction(self.menu_Presentation.menuAction())
        self.menubar.addAction(self.menu_View.menuAction())
        self.menubar.addAction(self.menu_Settings.menuAction())
        self.menubar.addAction(self.menu_Tools.menuAction())
        self.menubar.addAction(self.menu_Developer.menuAction())
        self.menu_File.addAction(self.actionNew)
        self.menu_File.addAction(self.actionLoad)
        self.menu_File.addAction(self.actionSave)
        self.menu_File.addAction(self.actionSave_As)
        self.menu_File.addSeparator()
        self.menu_File.addAction(self.recent_files_menu.menuAction())
        self.menu_File.addSeparator()
        self.menu_Edit.addAction(self.actionUndo)
        self.menu_Edit.addAction(self.actionRedo)
        self.menu_Presentation.addAction(self.actionGo_Live)
        self.menu_Presentation.addAction(self.actionAdd_New_Section)
        self.menu_Presentation.addSeparator()
        self.menu_Presentation.addAction(self.actionSection_Manager_PMenu)
        self.menu_View.addAction(self.actionSection_Manager_VMenu)
        self.menu_Settings.addAction(self.actionOpen_Settings)
        self.menu_Tools.addAction(self.actionResource_Manager)
        self.menu_Developer.addSeparator()
        self.menu_Developer.addAction(self.actionEnable_Hover_Debug)
        self.menu_Developer.addAction(self.actionToggle_Dirty_State_Debug)
        self.menu_Developer.addAction(self.actionShow_Environment_Variables)
        self.menu_Developer.addSeparator()
        self.menu_Developer.addAction(self.actionRun_Compositing_Test)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Plucky Presentation", None))
        self.actionNew.setText(QCoreApplication.translate("MainWindow", u"New", None))
        self.actionLoad.setText(QCoreApplication.translate("MainWindow", u"Load", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Save As...", None))
        self.actionUndo.setText(QCoreApplication.translate("MainWindow", u"Undo", None))
#if QT_CONFIG(shortcut)
        self.actionUndo.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Z", None))
#endif // QT_CONFIG(shortcut)
        self.actionRedo.setText(QCoreApplication.translate("MainWindow", u"Redo", None))
        self.actionGo_Live.setText(QCoreApplication.translate("MainWindow", u"Go Live", None))
        self.actionAdd_New_Section.setText(QCoreApplication.translate("MainWindow", u"Add New Section", None))
#if QT_CONFIG(tooltip)
        self.actionAdd_New_Section.setToolTip(QCoreApplication.translate("MainWindow", u"Add a new song or content section to the presentation.", None))
#endif // QT_CONFIG(tooltip)
        self.actionSection_Manager_PMenu.setText(QCoreApplication.translate("MainWindow", u"Section Manager", None))
#if QT_CONFIG(tooltip)
        self.actionSection_Manager_PMenu.setToolTip(QCoreApplication.translate("MainWindow", u"Show/Hide the Section Manager panel", None))
#endif // QT_CONFIG(tooltip)
        self.actionSection_Manager_VMenu.setText(QCoreApplication.translate("MainWindow", u"Section Manager", None))
        self.actionOpen_Settings.setText(QCoreApplication.translate("MainWindow", u"Open Settings...", None))
        self.actionResource_Manager.setText(QCoreApplication.translate("MainWindow", u"Resource Manager...", None))
        self.actionEnable_Hover_Debug.setText(QCoreApplication.translate("MainWindow", u"Enable Hover Debug", None))
        self.actionToggle_Dirty_State_Debug.setText(QCoreApplication.translate("MainWindow", u"Toggle Dirty State (Debug)", None))
        self.actionShow_Environment_Variables.setText(QCoreApplication.translate("MainWindow", u"Show Environment Variables", None))
        self.actionRun_Compositing_Test.setText(QCoreApplication.translate("MainWindow", u"Run Compositing Test", None))
        self.label_preview_size.setText(QCoreApplication.translate("MainWindow", u"Preview Size:", None))
#if QT_CONFIG(tooltip)
        self.preview_size_spinbox.setToolTip(QCoreApplication.translate("MainWindow", u"Adjust Slide Preview Size (1x-4x)", None))
#endif // QT_CONFIG(tooltip)
        self.preview_size_spinbox.setSuffix(QCoreApplication.translate("MainWindow", u"x", None))
#if QT_CONFIG(tooltip)
        self.dirty_indicator_label.setToolTip(QCoreApplication.translate("MainWindow", u"Presentation dirty status", None))
#endif // QT_CONFIG(tooltip)
        self.dirty_indicator_label.setText("")
#if QT_CONFIG(tooltip)
        self.edit_template_button.setToolTip(QCoreApplication.translate("MainWindow", u"Open the template editor.", None))
#endif // QT_CONFIG(tooltip)
        self.edit_template_button.setText(QCoreApplication.translate("MainWindow", u"Edit Templates", None))
        self.undo_button.setText(QCoreApplication.translate("MainWindow", u"Undo", None))
        self.redo_button.setText(QCoreApplication.translate("MainWindow", u"Redo", None))
        self.label_dl_output.setText(QCoreApplication.translate("MainWindow", u"DL Output", None))
        self.decklink_output_toggle_button.setText("")
        self.label_output.setText(QCoreApplication.translate("MainWindow", u"Output", None))
        self.go_live_button.setText("")
        self.label_slides.setText(QCoreApplication.translate("MainWindow", u"Slides:", None))
        self.menu_File.setTitle(QCoreApplication.translate("MainWindow", u"&File", None))
        self.recent_files_menu.setTitle(QCoreApplication.translate("MainWindow", u"Recents", None))
        self.menu_Edit.setTitle(QCoreApplication.translate("MainWindow", u"&Edit", None))
        self.menu_Presentation.setTitle(QCoreApplication.translate("MainWindow", u"&Presentation", None))
        self.menu_View.setTitle(QCoreApplication.translate("MainWindow", u"&View", None))
        self.menu_Settings.setTitle(QCoreApplication.translate("MainWindow", u"&Settings", None))
        self.menu_Tools.setTitle(QCoreApplication.translate("MainWindow", u"&Tools", None))
        self.menu_Developer.setTitle(QCoreApplication.translate("MainWindow", u"&Developer", None))
        self.SectionManagementDock.setWindowTitle(QCoreApplication.translate("MainWindow", u"Section Manager", None))
        self.media_pool_panel.setWindowTitle(QCoreApplication.translate("MainWindow", u"Media Pool", None))
    # retranslateUi

