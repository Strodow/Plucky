# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'slide_editor_item.ui'
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
    QLabel, QLayout, QPushButton, QSizePolicy,
    QSpacerItem, QTextEdit, QVBoxLayout, QWidget)

class Ui_SlideEditorItem(object):
    def setupUi(self, SlideEditorItem):
        if not SlideEditorItem.objectName():
            SlideEditorItem.setObjectName(u"SlideEditorItem")
        SlideEditorItem.resize(700, 343)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(SlideEditorItem.sizePolicy().hasHeightForWidth())
        SlideEditorItem.setSizePolicy(sizePolicy)
        self.root_vertical_layout = QVBoxLayout(SlideEditorItem)
        self.root_vertical_layout.setObjectName(u"root_vertical_layout")
        self.root_vertical_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.banner_content_frame = QFrame(SlideEditorItem)
        self.banner_content_frame.setObjectName(u"banner_content_frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.banner_content_frame.sizePolicy().hasHeightForWidth())
        self.banner_content_frame.setSizePolicy(sizePolicy1)
        self.banner_content_frame.setStyleSheet(u" padding: 4px; font-weight: bold; border-bottom: 1px solid #c0c0c0;")
        self.banner_content_frame.setFrameShape(QFrame.StyledPanel)
        self.banner_content_frame.setFrameShadow(QFrame.Raised)
        self.banner_layout = QHBoxLayout(self.banner_content_frame)
        self.banner_layout.setObjectName(u"banner_layout")
        self.banner_layout.setContentsMargins(2, 0, 2, 0)
        self.slide_name_banner_label = QLabel(self.banner_content_frame)
        self.slide_name_banner_label.setObjectName(u"slide_name_banner_label")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(1)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.slide_name_banner_label.sizePolicy().hasHeightForWidth())
        self.slide_name_banner_label.setSizePolicy(sizePolicy2)
        self.slide_name_banner_label.setStyleSheet(u"font-weight: bold;")
        self.slide_name_banner_label.setAlignment(Qt.AlignCenter)

        self.banner_layout.addWidget(self.slide_name_banner_label)

        self.banner_center_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.banner_layout.addItem(self.banner_center_spacer)

        self.banner_color_picker_button = QPushButton(self.banner_content_frame)
        self.banner_color_picker_button.setObjectName(u"banner_color_picker_button")
        self.banner_color_picker_button.setMinimumSize(QSize(30, 0))
        self.banner_color_picker_button.setMaximumSize(QSize(30, 16777215))

        self.banner_layout.addWidget(self.banner_color_picker_button)

        self.plus_button = QPushButton(self.banner_content_frame)
        self.plus_button.setObjectName(u"plus_button")
        self.plus_button.setMinimumSize(QSize(30, 0))
        self.plus_button.setMaximumSize(QSize(30, 16777215))

        self.banner_layout.addWidget(self.plus_button)

        self.minus_button = QPushButton(self.banner_content_frame)
        self.minus_button.setObjectName(u"minus_button")
        self.minus_button.setMinimumSize(QSize(30, 0))
        self.minus_button.setMaximumSize(QSize(30, 16777215))

        self.banner_layout.addWidget(self.minus_button)


        self.root_vertical_layout.addWidget(self.banner_content_frame)

        self.main_item_layout = QHBoxLayout()
        self.main_item_layout.setObjectName(u"main_item_layout")
        self.slide_template_and_preview_layout = QVBoxLayout()
        self.slide_template_and_preview_layout.setObjectName(u"slide_template_and_preview_layout")
        self.templates_combo_box_per_slide = QComboBox(SlideEditorItem)
        self.templates_combo_box_per_slide.addItem("")
        self.templates_combo_box_per_slide.addItem("")
        self.templates_combo_box_per_slide.addItem("")
        self.templates_combo_box_per_slide.addItem("")
        self.templates_combo_box_per_slide.setObjectName(u"templates_combo_box_per_slide")

        self.slide_template_and_preview_layout.addWidget(self.templates_combo_box_per_slide)

        self.slide_preview_label = QLabel(SlideEditorItem)
        self.slide_preview_label.setObjectName(u"slide_preview_label")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.slide_preview_label.sizePolicy().hasHeightForWidth())
        self.slide_preview_label.setSizePolicy(sizePolicy3)
        self.slide_preview_label.setMinimumSize(QSize(320, 180))
        self.slide_preview_label.setStyleSheet(u"border: 1px solid gray;")
        self.slide_preview_label.setScaledContents(False)
        self.slide_preview_label.setAlignment(Qt.AlignCenter)
        self.slide_preview_label.setWordWrap(True)

        self.slide_template_and_preview_layout.addWidget(self.slide_preview_label)


        self.main_item_layout.addLayout(self.slide_template_and_preview_layout)

        self.green_boxes_layout = QVBoxLayout()
        self.green_boxes_layout.setObjectName(u"green_boxes_layout")
        self.text_box_one_container_layout = QVBoxLayout()
        self.text_box_one_container_layout.setObjectName(u"text_box_one_container_layout")
        self.text_box_one_label = QLabel(SlideEditorItem)
        self.text_box_one_label.setObjectName(u"text_box_one_label")
        self.text_box_one_label.setWordWrap(True)

        self.text_box_one_container_layout.addWidget(self.text_box_one_label)

        self.vertical_spacer_text_box_one = QSpacerItem(20, 5, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.text_box_one_container_layout.addItem(self.vertical_spacer_text_box_one)

        self.text_box_one_edit = QTextEdit(SlideEditorItem)
        self.text_box_one_edit.setObjectName(u"text_box_one_edit")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.text_box_one_edit.sizePolicy().hasHeightForWidth())
        self.text_box_one_edit.setSizePolicy(sizePolicy4)
        self.text_box_one_edit.setMinimumSize(QSize(0, 20))
        self.text_box_one_edit.setStyleSheet(u"")
        self.text_box_one_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.text_box_one_container_layout.addWidget(self.text_box_one_edit)


        self.green_boxes_layout.addLayout(self.text_box_one_container_layout)

        self.text_box_two_container_layout = QVBoxLayout()
        self.text_box_two_container_layout.setObjectName(u"text_box_two_container_layout")
        self.text_box_two_label = QLabel(SlideEditorItem)
        self.text_box_two_label.setObjectName(u"text_box_two_label")
        self.text_box_two_label.setWordWrap(True)

        self.text_box_two_container_layout.addWidget(self.text_box_two_label)

        self.vertical_spacer_text_box_two = QSpacerItem(20, 5, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.text_box_two_container_layout.addItem(self.vertical_spacer_text_box_two)

        self.text_box_two_edit = QTextEdit(SlideEditorItem)
        self.text_box_two_edit.setObjectName(u"text_box_two_edit")
        sizePolicy4.setHeightForWidth(self.text_box_two_edit.sizePolicy().hasHeightForWidth())
        self.text_box_two_edit.setSizePolicy(sizePolicy4)
        self.text_box_two_edit.setStyleSheet(u"")
        self.text_box_two_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.text_box_two_container_layout.addWidget(self.text_box_two_edit)


        self.green_boxes_layout.addLayout(self.text_box_two_container_layout)

        self.text_box_three_container_layout = QVBoxLayout()
        self.text_box_three_container_layout.setObjectName(u"text_box_three_container_layout")
        self.text_box_three_label = QLabel(SlideEditorItem)
        self.text_box_three_label.setObjectName(u"text_box_three_label")
        self.text_box_three_label.setWordWrap(True)

        self.text_box_three_container_layout.addWidget(self.text_box_three_label)

        self.vertical_spacer_text_box_three = QSpacerItem(20, 5, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.text_box_three_container_layout.addItem(self.vertical_spacer_text_box_three)

        self.text_box_three_edit = QTextEdit(SlideEditorItem)
        self.text_box_three_edit.setObjectName(u"text_box_three_edit")
        sizePolicy4.setHeightForWidth(self.text_box_three_edit.sizePolicy().hasHeightForWidth())
        self.text_box_three_edit.setSizePolicy(sizePolicy4)
        self.text_box_three_edit.setStyleSheet(u"")
        self.text_box_three_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.text_box_three_container_layout.addWidget(self.text_box_three_edit)


        self.green_boxes_layout.addLayout(self.text_box_three_container_layout)

        self.green_boxes_bottom_spacer = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.green_boxes_layout.addItem(self.green_boxes_bottom_spacer)


        self.main_item_layout.addLayout(self.green_boxes_layout)


        self.root_vertical_layout.addLayout(self.main_item_layout)


        self.retranslateUi(SlideEditorItem)

        QMetaObject.connectSlotsByName(SlideEditorItem)
    # setupUi

    def retranslateUi(self, SlideEditorItem):
        SlideEditorItem.setWindowTitle(QCoreApplication.translate("SlideEditorItem", u"Form", None))
        self.slide_name_banner_label.setText(QCoreApplication.translate("SlideEditorItem", u"Slide Name Banner", None))
        self.banner_color_picker_button.setText(QCoreApplication.translate("SlideEditorItem", u"C", None))
        self.plus_button.setText(QCoreApplication.translate("SlideEditorItem", u"+", None))
        self.minus_button.setText(QCoreApplication.translate("SlideEditorItem", u"-", None))
        self.templates_combo_box_per_slide.setItemText(0, QCoreApplication.translate("SlideEditorItem", u"Default (3 Text Boxes)", None))
        self.templates_combo_box_per_slide.setItemText(1, QCoreApplication.translate("SlideEditorItem", u"Title Only", None))
        self.templates_combo_box_per_slide.setItemText(2, QCoreApplication.translate("SlideEditorItem", u"2 Text Boxes", None))
        self.templates_combo_box_per_slide.setItemText(3, QCoreApplication.translate("SlideEditorItem", u"Image + Text", None))

        self.slide_preview_label.setText(QCoreApplication.translate("SlideEditorItem", u"Slide Preview", None))
        self.text_box_one_label.setText(QCoreApplication.translate("SlideEditorItem", u"Text Box One:", None))
        self.text_box_two_label.setText(QCoreApplication.translate("SlideEditorItem", u"Text Box Two:", None))
        self.text_box_three_label.setText(QCoreApplication.translate("SlideEditorItem", u"Text Box Three:", None))
    # retranslateUi

