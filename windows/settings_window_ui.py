# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings_window.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialogButtonBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QTabWidget, QVBoxLayout, QWidget)

class Ui_SettingsUI(object):
    def setupUi(self, settingsWidget):
        if not settingsWidget.objectName():
            settingsWidget.setObjectName(u"settingsWidget")
        self.verticalLayout = QVBoxLayout(settingsWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabWidget = QTabWidget(settingsWidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.generalTab = QWidget()
        self.generalTab.setObjectName(u"generalTab")
        self.verticalLayout_2 = QVBoxLayout(self.generalTab)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.outputMonitorGroupBox = QGroupBox(self.generalTab)
        self.outputMonitorGroupBox.setObjectName(u"outputMonitorGroupBox")
        self.horizontalLayout = QHBoxLayout(self.outputMonitorGroupBox)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_output_monitor = QLabel(self.outputMonitorGroupBox)
        self.label_output_monitor.setObjectName(u"label_output_monitor")

        self.horizontalLayout.addWidget(self.label_output_monitor)

        self.monitorSelectionComboBox = QComboBox(self.outputMonitorGroupBox)
        self.monitorSelectionComboBox.setObjectName(u"monitorSelectionComboBox")

        self.horizontalLayout.addWidget(self.monitorSelectionComboBox)

        self.refreshMonitorsButton = QPushButton(self.outputMonitorGroupBox)
        self.refreshMonitorsButton.setObjectName(u"refreshMonitorsButton")

        self.horizontalLayout.addWidget(self.refreshMonitorsButton)


        self.verticalLayout_2.addWidget(self.outputMonitorGroupBox)

        self.decklinkOutputGroupBox = QGroupBox(self.generalTab)
        self.decklinkOutputGroupBox.setObjectName(u"decklinkOutputGroupBox")
        self.gridLayout_decklink = QGridLayout(self.decklinkOutputGroupBox)
        self.gridLayout_decklink.setObjectName(u"gridLayout_decklink")
        self.label_decklink_fill_device = QLabel(self.decklinkOutputGroupBox)
        self.label_decklink_fill_device.setObjectName(u"label_decklink_fill_device")

        self.gridLayout_decklink.addWidget(self.label_decklink_fill_device, 0, 0, 1, 1)

        self.decklinkFillDeviceComboBox = QComboBox(self.decklinkOutputGroupBox)
        self.decklinkFillDeviceComboBox.setObjectName(u"decklinkFillDeviceComboBox")

        self.gridLayout_decklink.addWidget(self.decklinkFillDeviceComboBox, 0, 1, 1, 1)

        self.refreshDecklinkDevicesButton = QPushButton(self.decklinkOutputGroupBox)
        self.refreshDecklinkDevicesButton.setObjectName(u"refreshDecklinkDevicesButton")

        self.gridLayout_decklink.addWidget(self.refreshDecklinkDevicesButton, 0, 2, 1, 1)

        self.label_decklink_key_device = QLabel(self.decklinkOutputGroupBox)
        self.label_decklink_key_device.setObjectName(u"label_decklink_key_device")

        self.gridLayout_decklink.addWidget(self.label_decklink_key_device, 1, 0, 1, 1)

        self.decklinkKeyDeviceComboBox = QComboBox(self.decklinkOutputGroupBox)
        self.decklinkKeyDeviceComboBox.setObjectName(u"decklinkKeyDeviceComboBox")

        self.gridLayout_decklink.addWidget(self.decklinkKeyDeviceComboBox, 1, 1, 1, 1)

        self.label_decklink_video_mode = QLabel(self.decklinkOutputGroupBox)
        self.label_decklink_video_mode.setObjectName(u"label_decklink_video_mode")

        self.gridLayout_decklink.addWidget(self.label_decklink_video_mode, 2, 0, 1, 1)

        self.decklinkVideoModeComboBox = QComboBox(self.decklinkOutputGroupBox)
        self.decklinkVideoModeComboBox.setObjectName(u"decklinkVideoModeComboBox")
        self.decklinkVideoModeComboBox.setEnabled(False)

        self.gridLayout_decklink.addWidget(self.decklinkVideoModeComboBox, 2, 1, 1, 1)


        self.verticalLayout_2.addWidget(self.decklinkOutputGroupBox)

        self.verticalSpacer_general = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer_general)

        self.tabWidget.addTab(self.generalTab, "")
        self.slideDefaultsTab = QWidget()
        self.slideDefaultsTab.setObjectName(u"slideDefaultsTab")
        self.slideDefaultsLayout = QVBoxLayout(self.slideDefaultsTab)
        self.slideDefaultsLayout.setObjectName(u"slideDefaultsLayout")
        self.newSlideDefaultGroupBox = QGroupBox(self.slideDefaultsTab)
        self.newSlideDefaultGroupBox.setObjectName(u"newSlideDefaultGroupBox")
        self.newSlideDefaultHLayout = QHBoxLayout(self.newSlideDefaultGroupBox)
        self.newSlideDefaultHLayout.setObjectName(u"newSlideDefaultHLayout")
        self.label_defaultTemplate = QLabel(self.newSlideDefaultGroupBox)
        self.label_defaultTemplate.setObjectName(u"label_defaultTemplate")

        self.newSlideDefaultHLayout.addWidget(self.label_defaultTemplate)

        self.defaultTemplateComboBox = QComboBox(self.newSlideDefaultGroupBox)
        self.defaultTemplateComboBox.setObjectName(u"defaultTemplateComboBox")

        self.newSlideDefaultHLayout.addWidget(self.defaultTemplateComboBox)

        self.horizontalSpacer_slideDefaults = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.newSlideDefaultHLayout.addItem(self.horizontalSpacer_slideDefaults)


        self.slideDefaultsLayout.addWidget(self.newSlideDefaultGroupBox)

        self.verticalSpacer_slideDefaults = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.slideDefaultsLayout.addItem(self.verticalSpacer_slideDefaults)

        self.tabWidget.addTab(self.slideDefaultsTab, "")
        self.developerTab = QWidget()
        self.developerTab.setObjectName(u"developerTab")
        self.developerTabLayout = QVBoxLayout(self.developerTab)
        self.developerTabLayout.setObjectName(u"developerTabLayout")
        self.ProdToggleGroupBox = QGroupBox(self.developerTab)
        self.ProdToggleGroupBox.setObjectName(u"ProdToggleGroupBox")
        self.horizontalLayout1 = QHBoxLayout(self.ProdToggleGroupBox)
        self.horizontalLayout1.setObjectName(u"horizontalLayout1")
        self.label_prod_toggle = QLabel(self.ProdToggleGroupBox)
        self.label_prod_toggle.setObjectName(u"label_prod_toggle")

        self.horizontalLayout1.addWidget(self.label_prod_toggle)

        self.ProdToggleComboBox = QComboBox(self.ProdToggleGroupBox)
        self.ProdToggleComboBox.setObjectName(u"ProdToggleComboBox")

        self.horizontalLayout1.addWidget(self.ProdToggleComboBox)


        self.developerTabLayout.addWidget(self.ProdToggleGroupBox)

        self.verticalSpacer_general1 = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.developerTabLayout.addItem(self.verticalSpacer_general1)

        self.benchmarkingGroupBox = QGroupBox(self.developerTab)
        self.benchmarkingGroupBox.setObjectName(u"benchmarkingGroupBox")
        self.benchmarkingGroupBox.setCheckable(True)
        self.benchmarkingGroupBox.setChecked(False)
        self.benchmarkingLayout = QVBoxLayout(self.benchmarkingGroupBox)
        self.benchmarkingLayout.setObjectName(u"benchmarkingLayout")
        self.label_app_init_time = QLabel(self.benchmarkingGroupBox)
        self.label_app_init_time.setObjectName(u"label_app_init_time")

        self.benchmarkingLayout.addWidget(self.label_app_init_time)

        self.label_mw_init_time = QLabel(self.benchmarkingGroupBox)
        self.label_mw_init_time.setObjectName(u"label_mw_init_time")

        self.benchmarkingLayout.addWidget(self.label_mw_init_time)

        self.label_mw_show_time = QLabel(self.benchmarkingGroupBox)
        self.label_mw_show_time.setObjectName(u"label_mw_show_time")

        self.benchmarkingLayout.addWidget(self.label_mw_show_time)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.benchmarkingLayout.addItem(self.verticalSpacer)

        self.label_last_presentation_path = QLabel(self.benchmarkingGroupBox)
        self.label_last_presentation_path.setObjectName(u"label_last_presentation_path")

        self.benchmarkingLayout.addWidget(self.label_last_presentation_path)

        self.label_pm_load_time = QLabel(self.benchmarkingGroupBox)
        self.label_pm_load_time.setObjectName(u"label_pm_load_time")

        self.benchmarkingLayout.addWidget(self.label_pm_load_time)

        self.label_ui_update_time = QLabel(self.benchmarkingGroupBox)
        self.label_ui_update_time.setObjectName(u"label_ui_update_time")

        self.benchmarkingLayout.addWidget(self.label_ui_update_time)

        self.label_render_total = QLabel(self.benchmarkingGroupBox)
        self.label_render_total.setObjectName(u"label_render_total")

        self.benchmarkingLayout.addWidget(self.label_render_total)

        self.label_render_images = QLabel(self.benchmarkingGroupBox)
        self.label_render_images.setObjectName(u"label_render_images")

        self.benchmarkingLayout.addWidget(self.label_render_images)

        self.label_render_fonts = QLabel(self.benchmarkingGroupBox)
        self.label_render_fonts.setObjectName(u"label_render_fonts")

        self.benchmarkingLayout.addWidget(self.label_render_fonts)

        self.label_render_layout = QLabel(self.benchmarkingGroupBox)
        self.label_render_layout.setObjectName(u"label_render_layout")

        self.benchmarkingLayout.addWidget(self.label_render_layout)

        self.label_render_draw = QLabel(self.benchmarkingGroupBox)
        self.label_render_draw.setObjectName(u"label_render_draw")

        self.benchmarkingLayout.addWidget(self.label_render_draw)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.benchmarkingLayout.addItem(self.verticalSpacer_2)


        self.developerTabLayout.addWidget(self.benchmarkingGroupBox)

        self.verticalSpacer_3 = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.developerTabLayout.addItem(self.verticalSpacer_3)

        self.tabWidget.addTab(self.developerTab, "")
        self.backupSharingTab = QWidget()
        self.backupSharingTab.setObjectName(u"backupSharingTab")
        self.backupSharingLayout = QVBoxLayout(self.backupSharingTab)
        self.backupSharingLayout.setObjectName(u"backupSharingLayout")
        self.backupStatusLabel = QLabel(self.backupSharingTab)
        self.backupStatusLabel.setObjectName(u"backupStatusLabel")
        font = QFont()
        font.setBold(True)
        self.backupStatusLabel.setFont(font)
        self.backupStatusLabel.setAlignment(Qt.AlignCenter)

        self.backupSharingLayout.addWidget(self.backupStatusLabel)

        self.unconfiguredRepoWidget = QWidget(self.backupSharingTab)
        self.unconfiguredRepoWidget.setObjectName(u"unconfiguredRepoWidget")
        self.unconfiguredRepoLayout = QVBoxLayout(self.unconfiguredRepoWidget)
        self.unconfiguredRepoLayout.setObjectName(u"unconfiguredRepoLayout")
        self.unconfiguredRepoLayout.setContentsMargins(0, 0, 0, 0)
        self.backupIntroLabel = QLabel(self.unconfiguredRepoWidget)
        self.backupIntroLabel.setObjectName(u"backupIntroLabel")
        self.backupIntroLabel.setAlignment(Qt.AlignCenter)
        self.backupIntroLabel.setWordWrap(True)
        self.backupIntroLabel.setMargin(10)

        self.unconfiguredRepoLayout.addWidget(self.backupIntroLabel)

        self.configureButtonLayout = QHBoxLayout()
        self.configureButtonLayout.setObjectName(u"configureButtonLayout")
        self.horizontalSpacer_configure_left = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.configureButtonLayout.addItem(self.horizontalSpacer_configure_left)

        self.setupNewRepoButton = QPushButton(self.unconfiguredRepoWidget)
        self.setupNewRepoButton.setObjectName(u"setupNewRepoButton")
        self.setupNewRepoButton.setMinimumSize(QSize(200, 0))

        self.configureButtonLayout.addWidget(self.setupNewRepoButton)

        self.horizontalSpacer_configure_right = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.configureButtonLayout.addItem(self.horizontalSpacer_configure_right)


        self.unconfiguredRepoLayout.addLayout(self.configureButtonLayout)

        self.existingRepoGroupBox = QGroupBox(self.unconfiguredRepoWidget)
        self.existingRepoGroupBox.setObjectName(u"existingRepoGroupBox")
        self.existingRepoFormLayout = QFormLayout(self.existingRepoGroupBox)
        self.existingRepoFormLayout.setObjectName(u"existingRepoFormLayout")
        self.label_existingRepoUrl = QLabel(self.existingRepoGroupBox)
        self.label_existingRepoUrl.setObjectName(u"label_existingRepoUrl")

        self.existingRepoFormLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_existingRepoUrl)

        self.existingRepoUrlLineEdit = QLineEdit(self.existingRepoGroupBox)
        self.existingRepoUrlLineEdit.setObjectName(u"existingRepoUrlLineEdit")

        self.existingRepoFormLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.existingRepoUrlLineEdit)

        self.connectExistingButtonLayout = QHBoxLayout()
        self.connectExistingButtonLayout.setObjectName(u"connectExistingButtonLayout")
        self.horizontalSpacer_connect_existing_left = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.connectExistingButtonLayout.addItem(self.horizontalSpacer_connect_existing_left)

        self.connectExistingRepoButton = QPushButton(self.existingRepoGroupBox)
        self.connectExistingRepoButton.setObjectName(u"connectExistingRepoButton")

        self.connectExistingButtonLayout.addWidget(self.connectExistingRepoButton)


        self.existingRepoFormLayout.setLayout(1, QFormLayout.ItemRole.FieldRole, self.connectExistingButtonLayout)


        self.unconfiguredRepoLayout.addWidget(self.existingRepoGroupBox)


        self.backupSharingLayout.addWidget(self.unconfiguredRepoWidget)

        self.configuredRepoWidget = QWidget(self.backupSharingTab)
        self.configuredRepoWidget.setObjectName(u"configuredRepoWidget")
        self.configuredRepoLayout = QVBoxLayout(self.configuredRepoWidget)
        self.configuredRepoLayout.setObjectName(u"configuredRepoLayout")
        self.configuredRepoLayout.setContentsMargins(0, 0, 0, 0)
        self.repoDetailsGroupBox = QGroupBox(self.configuredRepoWidget)
        self.repoDetailsGroupBox.setObjectName(u"repoDetailsGroupBox")
        self.repoDetailsLayout = QHBoxLayout(self.repoDetailsGroupBox)
        self.repoDetailsLayout.setObjectName(u"repoDetailsLayout")
        self.repoPathLabel = QLabel(self.repoDetailsGroupBox)
        self.repoPathLabel.setObjectName(u"repoPathLabel")

        self.repoDetailsLayout.addWidget(self.repoPathLabel)

        self.repoPathLineEdit = QLineEdit(self.repoDetailsGroupBox)
        self.repoPathLineEdit.setObjectName(u"repoPathLineEdit")
        self.repoPathLineEdit.setReadOnly(True)

        self.repoDetailsLayout.addWidget(self.repoPathLineEdit)

        self.changeRepoButton = QPushButton(self.repoDetailsGroupBox)
        self.changeRepoButton.setObjectName(u"changeRepoButton")

        self.repoDetailsLayout.addWidget(self.changeRepoButton)


        self.configuredRepoLayout.addWidget(self.repoDetailsGroupBox)

        self.repoActionsGroupBox = QGroupBox(self.configuredRepoWidget)
        self.repoActionsGroupBox.setObjectName(u"repoActionsGroupBox")
        self.repoActionsLayout = QHBoxLayout(self.repoActionsGroupBox)
        self.repoActionsLayout.setObjectName(u"repoActionsLayout")
        self.repoActionsSpacerLeft = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.repoActionsLayout.addItem(self.repoActionsSpacerLeft)

        self.pullRepoButton = QPushButton(self.repoActionsGroupBox)
        self.pullRepoButton.setObjectName(u"pullRepoButton")

        self.repoActionsLayout.addWidget(self.pullRepoButton)

        self.pushRepoButton = QPushButton(self.repoActionsGroupBox)
        self.pushRepoButton.setObjectName(u"pushRepoButton")

        self.repoActionsLayout.addWidget(self.pushRepoButton)

        self.commitRepoButton = QPushButton(self.repoActionsGroupBox)
        self.commitRepoButton.setObjectName(u"commitRepoButton")

        self.repoActionsLayout.addWidget(self.commitRepoButton)


        self.configuredRepoLayout.addWidget(self.repoActionsGroupBox)


        self.backupSharingLayout.addWidget(self.configuredRepoWidget)

        self.verticalSpacer_backupSharing = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.backupSharingLayout.addItem(self.verticalSpacer_backupSharing)

        self.tabWidget.addTab(self.backupSharingTab, "")

        self.verticalLayout.addWidget(self.tabWidget)

        self.buttonBox = QDialogButtonBox(settingsWidget)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(settingsWidget)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(settingsWidget)
    # setupUi

    def retranslateUi(self, settingsWidget):
        self.outputMonitorGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Output Monitor", None))
        self.label_output_monitor.setText(QCoreApplication.translate("SettingsUI", u"Select Monitor:", None))
        self.refreshMonitorsButton.setText(QCoreApplication.translate("SettingsUI", u"Refresh", None))
        self.decklinkOutputGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"DeckLink Output", None))
        self.label_decklink_fill_device.setText(QCoreApplication.translate("SettingsUI", u"Fill Device:", None))
        self.refreshDecklinkDevicesButton.setText(QCoreApplication.translate("SettingsUI", u"Refresh", None))
#if QT_CONFIG(tooltip)
        self.refreshDecklinkDevicesButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Refresh the list of available DeckLink devices.", None))
#endif // QT_CONFIG(tooltip)
        self.label_decklink_key_device.setText(QCoreApplication.translate("SettingsUI", u"Key Device:", None))
        self.label_decklink_video_mode.setText(QCoreApplication.translate("SettingsUI", u"Video Mode:", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.generalTab), QCoreApplication.translate("SettingsUI", u"General", None))
        self.newSlideDefaultGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"New Slide Default Template", None))
        self.label_defaultTemplate.setText(QCoreApplication.translate("SettingsUI", u"Default Template:", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.slideDefaultsTab), QCoreApplication.translate("SettingsUI", u"Slide Defaults", None))
        self.ProdToggleGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Prod Toggle", None))
        self.label_prod_toggle.setText(QCoreApplication.translate("SettingsUI", u"Version:", None))
        self.benchmarkingGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Benchmarking", None))
        self.label_app_init_time.setText(QCoreApplication.translate("SettingsUI", u"App Init Time: N/A", None))
        self.label_mw_init_time.setText(QCoreApplication.translate("SettingsUI", u"MainWindow Init Time: N/A", None))
        self.label_mw_show_time.setText(QCoreApplication.translate("SettingsUI", u"MainWindow Show Time: N/A", None))
        self.label_last_presentation_path.setText(QCoreApplication.translate("SettingsUI", u"Last Presentation: None", None))
        self.label_pm_load_time.setText(QCoreApplication.translate("SettingsUI", u"PM Load Time: N/A", None))
#if QT_CONFIG(tooltip)
        self.label_pm_load_time.setToolTip(QCoreApplication.translate("SettingsUI", u"Time taken by the Presentation Manager to load the presentation file from disk and parse its content.", None))
#endif // QT_CONFIG(tooltip)
        self.label_ui_update_time.setText(QCoreApplication.translate("SettingsUI", u"UI Update Time: N/A", None))
#if QT_CONFIG(tooltip)
        self.label_ui_update_time.setToolTip(QCoreApplication.translate("SettingsUI", u"Time taken to update the main window's UI after a presentation is loaded, including rendering all slide previews.", None))
#endif // QT_CONFIG(tooltip)
        self.label_render_total.setText(QCoreApplication.translate("SettingsUI", u"Render (Total): N/A", None))
        self.label_render_images.setText(QCoreApplication.translate("SettingsUI", u"Render (Images): N/A", None))
        self.label_render_fonts.setText(QCoreApplication.translate("SettingsUI", u"Render (Fonts): N/A", None))
        self.label_render_layout.setText(QCoreApplication.translate("SettingsUI", u"Render (Layout): N/A", None))
        self.label_render_draw.setText(QCoreApplication.translate("SettingsUI", u"Render (Draw): N/A", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.developerTab), QCoreApplication.translate("SettingsUI", u"Developer", None))
        self.backupStatusLabel.setText(QCoreApplication.translate("SettingsUI", u"Status: Not Configured", None))
        self.backupIntroLabel.setText(QCoreApplication.translate("SettingsUI", u"Configure a Git repository to enable backup and sharing of your data. This allows you to keep your data synchronized across multiple devices or restore it easily.", None))
        self.setupNewRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Setup New Backup Location...", None))
#if QT_CONFIG(tooltip)
        self.setupNewRepoButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Set up a new backup location (creates a new bare Git repository).", None))
#endif // QT_CONFIG(tooltip)
        self.existingRepoGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Or Connect to Existing Remote Repository", None))
        self.label_existingRepoUrl.setText(QCoreApplication.translate("SettingsUI", u"Remote URL/Path:", None))
        self.existingRepoUrlLineEdit.setPlaceholderText(QCoreApplication.translate("SettingsUI", u"e.g., https://github.com/user/repo.git or /path/to/remote.git", None))
        self.connectExistingRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Connect", None))
#if QT_CONFIG(tooltip)
        self.connectExistingRepoButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Connect to an existing Git remote repository.", None))
#endif // QT_CONFIG(tooltip)
        self.repoDetailsGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Repository Details", None))
        self.repoPathLabel.setText(QCoreApplication.translate("SettingsUI", u"Path:", None))
        self.repoPathLineEdit.setPlaceholderText(QCoreApplication.translate("SettingsUI", u"N/A", None))
        self.changeRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Change/Reconfigure...", None))
        self.repoActionsGroupBox.setTitle(QCoreApplication.translate("SettingsUI", u"Repository Actions", None))
        self.pullRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Pull", None))
#if QT_CONFIG(tooltip)
        self.pullRepoButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Fetch and integrate the latest changes from the remote repository.", None))
#endif // QT_CONFIG(tooltip)
        self.pushRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Push", None))
#if QT_CONFIG(tooltip)
        self.pushRepoButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Upload local commits to the remote repository.", None))
#endif // QT_CONFIG(tooltip)
        self.commitRepoButton.setText(QCoreApplication.translate("SettingsUI", u"Commit...", None))
#if QT_CONFIG(tooltip)
        self.commitRepoButton.setToolTip(QCoreApplication.translate("SettingsUI", u"Stage and commit local changes.", None))
#endif // QT_CONFIG(tooltip)
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.backupSharingTab), QCoreApplication.translate("SettingsUI", u"Backup & Sharing", None))
        pass
    # retranslateUi

