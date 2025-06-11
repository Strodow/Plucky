# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_editor_window.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QSplitter, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1000, 800)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.root_vertical_layout_for_banner_and_splitter = QVBoxLayout(self.centralwidget)
        self.root_vertical_layout_for_banner_and_splitter.setObjectName(u"root_vertical_layout_for_banner_and_splitter")
        self.top_banner_layout = QHBoxLayout()
        self.top_banner_layout.setObjectName(u"top_banner_layout")
        self.section_title_banner_label = QLabel(self.centralwidget)
        self.section_title_banner_label.setObjectName(u"section_title_banner_label")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.section_title_banner_label.sizePolicy().hasHeightForWidth())
        self.section_title_banner_label.setSizePolicy(sizePolicy)
        self.section_title_banner_label.setAlignment(Qt.AlignCenter)
        self.section_title_banner_label.setStyleSheet(u"font-size: 16pt; font-weight: bold; padding: 5px; border-bottom: 1px solid #aaaaaa;")

        self.top_banner_layout.addWidget(self.section_title_banner_label)


        self.root_vertical_layout_for_banner_and_splitter.addLayout(self.top_banner_layout)

        self.section_properties_group_box = QGroupBox(self.centralwidget)
        self.section_properties_group_box.setObjectName(u"section_properties_group_box")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.section_properties_group_box.sizePolicy().hasHeightForWidth())
        self.section_properties_group_box.setSizePolicy(sizePolicy1)
        self.section_properties_group_box.setCheckable(True)
        self.section_properties_group_box.setChecked(False)
        self.group_box_main_layout = QVBoxLayout(self.section_properties_group_box)
        self.group_box_main_layout.setObjectName(u"group_box_main_layout")
        self.section_properties_content_container = QWidget(self.section_properties_group_box)
        self.section_properties_content_container.setObjectName(u"section_properties_content_container")
        self.section_properties_content_layout = QVBoxLayout(self.section_properties_content_container)
        self.section_properties_content_layout.setObjectName(u"section_properties_content_layout")
        self.section_properties_content_layout.setContentsMargins(0, 0, 0, 0)
        self.metadata_entries_layout = QVBoxLayout()
        self.metadata_entries_layout.setObjectName(u"metadata_entries_layout")

        self.section_properties_content_layout.addLayout(self.metadata_entries_layout)

        self.add_metadata_button = QPushButton(self.section_properties_content_container)
        self.add_metadata_button.setObjectName(u"add_metadata_button")

        self.section_properties_content_layout.addWidget(self.add_metadata_button)

        self.metadata_vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.section_properties_content_layout.addItem(self.metadata_vertical_spacer)


        self.group_box_main_layout.addWidget(self.section_properties_content_container)


        self.root_vertical_layout_for_banner_and_splitter.addWidget(self.section_properties_group_box)

        self.main_splitter = QSplitter(self.centralwidget)
        self.main_splitter.setObjectName(u"main_splitter")
        self.main_splitter.setOrientation(Qt.Horizontal)
        self.left_panel_widget = QWidget(self.main_splitter)
        self.left_panel_widget.setObjectName(u"left_panel_widget")
        self.main_editor_area_layout = QVBoxLayout(self.left_panel_widget)
        self.main_editor_area_layout.setObjectName(u"main_editor_area_layout")
        self.main_editor_area_layout.setContentsMargins(0, 0, 0, 0)
        self.main_slides_scroll_area = QScrollArea(self.left_panel_widget)
        self.main_slides_scroll_area.setObjectName(u"main_slides_scroll_area")
        self.main_slides_scroll_area.setWidgetResizable(True)
        self.scrollAreaContentWidget = QWidget()
        self.scrollAreaContentWidget.setObjectName(u"scrollAreaContentWidget")
        self.scrollAreaContentWidget.setGeometry(QRect(0, 0, 698, 776))
        self.slides_container_layout = QVBoxLayout(self.scrollAreaContentWidget)
        self.slides_container_layout.setObjectName(u"slides_container_layout")
        self.main_slides_scroll_area.setWidget(self.scrollAreaContentWidget)

        self.main_editor_area_layout.addWidget(self.main_slides_scroll_area)

        self.main_splitter.addWidget(self.left_panel_widget)
        self.right_sidebar_frame = QFrame(self.main_splitter)
        self.right_sidebar_frame.setObjectName(u"right_sidebar_frame")
        self.right_sidebar_frame.setMinimumSize(QSize(150, 0))
        self.right_sidebar_frame.setFrameShape(QFrame.StyledPanel)
        self.right_sidebar_frame.setFrameShadow(QFrame.Raised)
        self.right_sidebar_layout = QVBoxLayout(self.right_sidebar_frame)
        self.right_sidebar_layout.setObjectName(u"right_sidebar_layout")
        self.save_sidebar_button = QPushButton(self.right_sidebar_frame)
        self.save_sidebar_button.setObjectName(u"save_sidebar_button")

        self.right_sidebar_layout.addWidget(self.save_sidebar_button)

        self.slides_label = QLabel(self.right_sidebar_frame)
        self.slides_label.setObjectName(u"slides_label")
        self.slides_label.setAlignment(Qt.AlignCenter)

        self.right_sidebar_layout.addWidget(self.slides_label)

        self.right_slides_scroll_area = QScrollArea(self.right_sidebar_frame)
        self.right_slides_scroll_area.setObjectName(u"right_slides_scroll_area")
        self.right_slides_scroll_area.setWidgetResizable(True)
        self.slide_thumbnails_list_widget = QListWidget()
        self.slide_thumbnails_list_widget.setObjectName(u"slide_thumbnails_list_widget")
        self.slide_thumbnails_list_widget.setGeometry(QRect(0, 0, 178, 746))
        self.slide_thumbnails_list_widget.setFrameShape(QFrame.NoFrame)
        self.slide_thumbnails_list_widget.setFrameShadow(QFrame.Plain)
        self.right_slides_scroll_area.setWidget(self.slide_thumbnails_list_widget)

        self.right_sidebar_layout.addWidget(self.right_slides_scroll_area)

        self.main_splitter.addWidget(self.right_sidebar_frame)

        self.root_vertical_layout_for_banner_and_splitter.addWidget(self.main_splitter)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Mass Slide Editor", None))
        self.section_title_banner_label.setText(QCoreApplication.translate("MainWindow", u"Section Title Banner", None))
        self.section_properties_group_box.setTitle(QCoreApplication.translate("MainWindow", u"Section Properties", None))
        self.add_metadata_button.setText(QCoreApplication.translate("MainWindow", u"Add Metadata Field", None))
        self.save_sidebar_button.setText(QCoreApplication.translate("MainWindow", u"Save Changes", None))
        self.slides_label.setText(QCoreApplication.translate("MainWindow", u"Slides", None))
    # retranslateUi

