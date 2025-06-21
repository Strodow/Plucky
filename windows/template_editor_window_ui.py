# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'template_editor_window.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFontComboBox, QFormLayout,
    QFrame, QGraphicsView, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_TemplateEditorWindow(object):
    def setupUi(self, TemplateEditorWindow):
        if not TemplateEditorWindow.objectName():
            TemplateEditorWindow.setObjectName(u"TemplateEditorWindow")
        TemplateEditorWindow.resize(1300, 600)
        self.main_v_layout = QVBoxLayout(TemplateEditorWindow)
        self.main_v_layout.setObjectName(u"main_v_layout")
        self.main_tab_widget = QTabWidget(TemplateEditorWindow)
        self.main_tab_widget.setObjectName(u"main_tab_widget")
        self.layouts_tab = QWidget()
        self.layouts_tab.setObjectName(u"layouts_tab")
        self.layouts_tab_v_layout = QVBoxLayout(self.layouts_tab)
        self.layouts_tab_v_layout.setObjectName(u"layouts_tab_v_layout")
        self.layout_selector_layout = QHBoxLayout()
        self.layout_selector_layout.setObjectName(u"layout_selector_layout")
        self.layout_selector_label = QLabel(self.layouts_tab)
        self.layout_selector_label.setObjectName(u"layout_selector_label")

        self.layout_selector_layout.addWidget(self.layout_selector_label)

        self.layout_selector_combo = QComboBox(self.layouts_tab)
        self.layout_selector_combo.setObjectName(u"layout_selector_combo")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.layout_selector_combo.sizePolicy().hasHeightForWidth())
        self.layout_selector_combo.setSizePolicy(sizePolicy)

        self.layout_selector_layout.addWidget(self.layout_selector_combo)

        self.add_layout_button = QPushButton(self.layouts_tab)
        self.add_layout_button.setObjectName(u"add_layout_button")
        self.add_layout_button.setMaximumSize(QSize(30, 16777215))

        self.layout_selector_layout.addWidget(self.add_layout_button)

        self.remove_layout_button = QPushButton(self.layouts_tab)
        self.remove_layout_button.setObjectName(u"remove_layout_button")
        self.remove_layout_button.setMaximumSize(QSize(30, 16777215))

        self.layout_selector_layout.addWidget(self.remove_layout_button)

        self.rename_layout_button = QPushButton(self.layouts_tab)
        self.rename_layout_button.setObjectName(u"rename_layout_button")
        self.rename_layout_button.setMaximumSize(QSize(30, 16777215))

        self.layout_selector_layout.addWidget(self.rename_layout_button)


        self.layouts_tab_v_layout.addLayout(self.layout_selector_layout)

        self.layout_editor_area_layout = QHBoxLayout()
        self.layout_editor_area_layout.setObjectName(u"layout_editor_area_layout")
        self.layout_preview_graphics_view = ZoomableGraphicsView(self.layouts_tab)
        self.layout_preview_graphics_view.setObjectName(u"layout_preview_graphics_view")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.layout_preview_graphics_view.sizePolicy().hasHeightForWidth())
        self.layout_preview_graphics_view.setSizePolicy(sizePolicy1)
        self.layout_preview_graphics_view.setMinimumSize(QSize(0, 250))
        self.layout_preview_graphics_view.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing)

        self.layout_editor_area_layout.addWidget(self.layout_preview_graphics_view)

        self.widget = QWidget(self.layouts_tab)
        self.widget.setObjectName(u"widget")
        self.vboxLayout = QVBoxLayout(self.widget)
        self.vboxLayout.setObjectName(u"vboxLayout")
        self.vboxLayout.setContentsMargins(0, 0, 0, 0)
        self.layout_background_group = QGroupBox(self.widget)
        self.layout_background_group.setObjectName(u"layout_background_group")
        self.layout_background_hbox = QHBoxLayout(self.layout_background_group)
        self.layout_background_hbox.setObjectName(u"layout_background_hbox")
        self.layout_bg_enable_checkbox = QCheckBox(self.layout_background_group)
        self.layout_bg_enable_checkbox.setObjectName(u"layout_bg_enable_checkbox")

        self.layout_background_hbox.addWidget(self.layout_bg_enable_checkbox)

        self.layout_bg_color_button = QPushButton(self.layout_background_group)
        self.layout_bg_color_button.setObjectName(u"layout_bg_color_button")

        self.layout_background_hbox.addWidget(self.layout_bg_color_button)

        self.layout_bg_color_swatch_label = QLabel(self.layout_background_group)
        self.layout_bg_color_swatch_label.setObjectName(u"layout_bg_color_swatch_label")
        self.layout_bg_color_swatch_label.setMinimumSize(QSize(24, 24))
        self.layout_bg_color_swatch_label.setMaximumSize(QSize(24, 24))
        self.layout_bg_color_swatch_label.setAutoFillBackground(True)
        self.layout_bg_color_swatch_label.setFrameShape(QFrame.StyledPanel)

        self.layout_background_hbox.addWidget(self.layout_bg_color_swatch_label)


        self.vboxLayout.addWidget(self.layout_background_group)

        self.layout_textbox_buttons_layout = QHBoxLayout()
        self.layout_textbox_buttons_layout.setObjectName(u"layout_textbox_buttons_layout")
        self.add_textbox_to_layout_button = QPushButton(self.widget)
        self.add_textbox_to_layout_button.setObjectName(u"add_textbox_to_layout_button")

        self.layout_textbox_buttons_layout.addWidget(self.add_textbox_to_layout_button)

        self.add_shape_button = QPushButton(self.widget)
        self.add_shape_button.setObjectName(u"add_shape_button")

        self.layout_textbox_buttons_layout.addWidget(self.add_shape_button)

        self.remove_selected_textbox_button = QPushButton(self.widget)
        self.remove_selected_textbox_button.setObjectName(u"remove_selected_textbox_button")

        self.layout_textbox_buttons_layout.addWidget(self.remove_selected_textbox_button)


        self.vboxLayout.addLayout(self.layout_textbox_buttons_layout)

        self.textbox_properties_group = QGroupBox(self.widget)
        self.textbox_properties_group.setObjectName(u"textbox_properties_group")
        self.textbox_properties_group.setEnabled(False)
        self.textbox_properties_form_layout = QFormLayout(self.textbox_properties_group)
        self.textbox_properties_form_layout.setObjectName(u"textbox_properties_form_layout")
        self.textbox_id_label = QLabel(self.textbox_properties_group)
        self.textbox_id_label.setObjectName(u"textbox_id_label")

        self.textbox_properties_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.textbox_id_label)

        self.selected_textbox_id_edit = QLineEdit(self.textbox_properties_group)
        self.selected_textbox_id_edit.setObjectName(u"selected_textbox_id_edit")

        self.textbox_properties_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.selected_textbox_id_edit)

        self.textbox_style_label = QLabel(self.textbox_properties_group)
        self.textbox_style_label.setObjectName(u"textbox_style_label")

        self.textbox_properties_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.textbox_style_label)

        self.selected_textbox_style_combo = QComboBox(self.textbox_properties_group)
        self.selected_textbox_style_combo.setObjectName(u"selected_textbox_style_combo")

        self.textbox_properties_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.selected_textbox_style_combo)

        self.label_halign = QLabel(self.textbox_properties_group)
        self.label_halign.setObjectName(u"label_halign")

        self.textbox_properties_form_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.label_halign)

        self.selected_textbox_halign_combo = QComboBox(self.textbox_properties_group)
        self.selected_textbox_halign_combo.setObjectName(u"selected_textbox_halign_combo")

        self.textbox_properties_form_layout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.selected_textbox_halign_combo)

        self.label_valign = QLabel(self.textbox_properties_group)
        self.label_valign.setObjectName(u"label_valign")

        self.textbox_properties_form_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.label_valign)

        self.selected_textbox_valign_combo = QComboBox(self.textbox_properties_group)
        self.selected_textbox_valign_combo.setObjectName(u"selected_textbox_valign_combo")

        self.textbox_properties_form_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.selected_textbox_valign_combo)

        self.textbox_properties_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.textbox_properties_form_layout.setItem(4, QFormLayout.ItemRole.LabelRole, self.textbox_properties_spacer)


        self.vboxLayout.addWidget(self.textbox_properties_group)

        self.layout_elements_group = QGroupBox(self.widget)
        self.layout_elements_group.setObjectName(u"layout_elements_group")
        self.verticalLayout_elements_group = QVBoxLayout(self.layout_elements_group)
        self.verticalLayout_elements_group.setObjectName(u"verticalLayout_elements_group")
        self.layout_elements_scroll_area = QScrollArea(self.layout_elements_group)
        self.layout_elements_scroll_area.setObjectName(u"layout_elements_scroll_area")
        self.layout_elements_scroll_area.setMinimumSize(QSize(0, 100))
        self.layout_elements_scroll_area.setWidgetResizable(True)
        self.layout_elements_scroll_content = QWidget()
        self.layout_elements_scroll_content.setObjectName(u"layout_elements_scroll_content")
        self.layout_elements_scroll_content.setGeometry(QRect(0, 0, 301, 96))
        self.layout_elements_list_layout = QVBoxLayout(self.layout_elements_scroll_content)
        self.layout_elements_list_layout.setObjectName(u"layout_elements_list_layout")
        self.layout_elements_scroll_area.setWidget(self.layout_elements_scroll_content)

        self.verticalLayout_elements_group.addWidget(self.layout_elements_scroll_area)


        self.vboxLayout.addWidget(self.layout_elements_group)

        self.shape_properties_group = QGroupBox(self.widget)
        self.shape_properties_group.setObjectName(u"shape_properties_group")
        self.shape_properties_group.setEnabled(False)
        self.shape_properties_form_layout = QFormLayout(self.shape_properties_group)
        self.shape_properties_form_layout.setObjectName(u"shape_properties_form_layout")
        self.shape_id_label = QLabel(self.shape_properties_group)
        self.shape_id_label.setObjectName(u"shape_id_label")

        self.shape_properties_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.shape_id_label)

        self.selected_shape_id_edit = QLineEdit(self.shape_properties_group)
        self.selected_shape_id_edit.setObjectName(u"selected_shape_id_edit")

        self.shape_properties_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.selected_shape_id_edit)

        self.shape_fill_color_label = QLabel(self.shape_properties_group)
        self.shape_fill_color_label.setObjectName(u"shape_fill_color_label")

        self.shape_properties_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.shape_fill_color_label)

        self.shape_fill_color_layout = QHBoxLayout()
        self.shape_fill_color_layout.setObjectName(u"shape_fill_color_layout")
        self.selected_shape_fill_color_button = QPushButton(self.shape_properties_group)
        self.selected_shape_fill_color_button.setObjectName(u"selected_shape_fill_color_button")

        self.shape_fill_color_layout.addWidget(self.selected_shape_fill_color_button)

        self.selected_shape_fill_color_swatch = QLabel(self.shape_properties_group)
        self.selected_shape_fill_color_swatch.setObjectName(u"selected_shape_fill_color_swatch")
        self.selected_shape_fill_color_swatch.setMinimumSize(QSize(24, 24))
        self.selected_shape_fill_color_swatch.setAutoFillBackground(True)
        self.selected_shape_fill_color_swatch.setFrameShape(QFrame.StyledPanel)

        self.shape_fill_color_layout.addWidget(self.selected_shape_fill_color_swatch)

        self.shape_fill_color_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.shape_fill_color_layout.addItem(self.shape_fill_color_spacer)


        self.shape_properties_form_layout.setLayout(1, QFormLayout.ItemRole.FieldRole, self.shape_fill_color_layout)

        self.shape_stroke_color_label = QLabel(self.shape_properties_group)
        self.shape_stroke_color_label.setObjectName(u"shape_stroke_color_label")

        self.shape_properties_form_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.shape_stroke_color_label)

        self.shape_stroke_color_layout = QHBoxLayout()
        self.shape_stroke_color_layout.setObjectName(u"shape_stroke_color_layout")
        self.selected_shape_stroke_color_button = QPushButton(self.shape_properties_group)
        self.selected_shape_stroke_color_button.setObjectName(u"selected_shape_stroke_color_button")

        self.shape_stroke_color_layout.addWidget(self.selected_shape_stroke_color_button)

        self.selected_shape_stroke_color_swatch = QLabel(self.shape_properties_group)
        self.selected_shape_stroke_color_swatch.setObjectName(u"selected_shape_stroke_color_swatch")
        self.selected_shape_stroke_color_swatch.setMinimumSize(QSize(24, 24))
        self.selected_shape_stroke_color_swatch.setAutoFillBackground(True)
        self.selected_shape_stroke_color_swatch.setFrameShape(QFrame.StyledPanel)

        self.shape_stroke_color_layout.addWidget(self.selected_shape_stroke_color_swatch)

        self.shape_stroke_color_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.shape_stroke_color_layout.addItem(self.shape_stroke_color_spacer)


        self.shape_properties_form_layout.setLayout(2, QFormLayout.ItemRole.FieldRole, self.shape_stroke_color_layout)

        self.shape_stroke_width_label = QLabel(self.shape_properties_group)
        self.shape_stroke_width_label.setObjectName(u"shape_stroke_width_label")

        self.shape_properties_form_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.shape_stroke_width_label)

        self.selected_shape_stroke_width_spinbox = QSpinBox(self.shape_properties_group)
        self.selected_shape_stroke_width_spinbox.setObjectName(u"selected_shape_stroke_width_spinbox")

        self.shape_properties_form_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.selected_shape_stroke_width_spinbox)


        self.vboxLayout.addWidget(self.shape_properties_group)

        self.right_panel_vertical_spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.vboxLayout.addItem(self.right_panel_vertical_spacer)


        self.layout_editor_area_layout.addWidget(self.widget)

        self.layout_editor_area_layout.setStretch(0, 3)
        self.layout_editor_area_layout.setStretch(1, 1)

        self.layouts_tab_v_layout.addLayout(self.layout_editor_area_layout)

        self.main_tab_widget.addTab(self.layouts_tab, "")
        self.styles_tab = QWidget()
        self.styles_tab.setObjectName(u"styles_tab")
        self.styles_tab_v_layout = QVBoxLayout(self.styles_tab)
        self.styles_tab_v_layout.setObjectName(u"styles_tab_v_layout")
        self.style_selector_layout = QHBoxLayout()
        self.style_selector_layout.setObjectName(u"style_selector_layout")
        self.style_selector_label = QLabel(self.styles_tab)
        self.style_selector_label.setObjectName(u"style_selector_label")

        self.style_selector_layout.addWidget(self.style_selector_label)

        self.style_selector_combo = QComboBox(self.styles_tab)
        self.style_selector_combo.setObjectName(u"style_selector_combo")
        sizePolicy.setHeightForWidth(self.style_selector_combo.sizePolicy().hasHeightForWidth())
        self.style_selector_combo.setSizePolicy(sizePolicy)

        self.style_selector_layout.addWidget(self.style_selector_combo)

        self.add_style_button = QPushButton(self.styles_tab)
        self.add_style_button.setObjectName(u"add_style_button")
        self.add_style_button.setMaximumSize(QSize(30, 16777215))

        self.style_selector_layout.addWidget(self.add_style_button)

        self.remove_style_button = QPushButton(self.styles_tab)
        self.remove_style_button.setObjectName(u"remove_style_button")
        self.remove_style_button.setMaximumSize(QSize(30, 16777215))

        self.style_selector_layout.addWidget(self.remove_style_button)


        self.styles_tab_v_layout.addLayout(self.style_selector_layout)

        self.style_properties_group = QGroupBox(self.styles_tab)
        self.style_properties_group.setObjectName(u"style_properties_group")
        self.verticalLayout = QVBoxLayout(self.style_properties_group)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.preview_text_input_label = QLabel(self.style_properties_group)
        self.preview_text_input_label.setObjectName(u"preview_text_input_label")

        self.verticalLayout.addWidget(self.preview_text_input_label)

        self.preview_text_input_edit = QLineEdit(self.style_properties_group)
        self.preview_text_input_edit.setObjectName(u"preview_text_input_edit")

        self.verticalLayout.addWidget(self.preview_text_input_edit)

        self.style_form_layout = QFormLayout()
        self.style_form_layout.setObjectName(u"style_form_layout")
        self.font_family_label = QLabel(self.style_properties_group)
        self.font_family_label.setObjectName(u"font_family_label")

        self.style_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.font_family_label)

        self.font_family_combo = QFontComboBox(self.style_properties_group)
        self.font_family_combo.setObjectName(u"font_family_combo")

        self.style_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.font_family_combo)

        self.font_size_label = QLabel(self.style_properties_group)
        self.font_size_label.setObjectName(u"font_size_label")

        self.style_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.font_size_label)

        self.font_size_spinbox = QSpinBox(self.style_properties_group)
        self.font_size_spinbox.setObjectName(u"font_size_spinbox")
        self.font_size_spinbox.setMinimum(6)
        self.font_size_spinbox.setMaximum(144)
        self.font_size_spinbox.setValue(12)

        self.style_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.font_size_spinbox)

        self.font_color_label = QLabel(self.style_properties_group)
        self.font_color_label.setObjectName(u"font_color_label")

        self.style_form_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.font_color_label)

        self.font_color_layout = QHBoxLayout()
        self.font_color_layout.setObjectName(u"font_color_layout")
        self.font_color_button = QPushButton(self.style_properties_group)
        self.font_color_button.setObjectName(u"font_color_button")

        self.font_color_layout.addWidget(self.font_color_button)

        self.font_color_preview_label = QLabel(self.style_properties_group)
        self.font_color_preview_label.setObjectName(u"font_color_preview_label")
        self.font_color_preview_label.setMinimumSize(QSize(24, 24))
        self.font_color_preview_label.setAutoFillBackground(True)
        self.font_color_preview_label.setFrameShape(QFrame.StyledPanel)

        self.font_color_layout.addWidget(self.font_color_preview_label)

        self.font_color_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.font_color_layout.addItem(self.font_color_spacer)


        self.style_form_layout.setLayout(2, QFormLayout.ItemRole.FieldRole, self.font_color_layout)

        self.force_caps_label = QLabel(self.style_properties_group)
        self.force_caps_label.setObjectName(u"force_caps_label")

        self.style_form_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.force_caps_label)

        self.force_caps_checkbox = QCheckBox(self.style_properties_group)
        self.force_caps_checkbox.setObjectName(u"force_caps_checkbox")

        self.style_form_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.force_caps_checkbox)

        self.text_shadow_checkbox = QCheckBox(self.style_properties_group)
        self.text_shadow_checkbox.setObjectName(u"text_shadow_checkbox")

        self.style_form_layout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.text_shadow_checkbox)

        self.shadow_properties_group = QGroupBox(self.style_properties_group)
        self.shadow_properties_group.setObjectName(u"shadow_properties_group")
        self.shadow_properties_group.setCheckable(False)
        self.shadow_form_layout = QFormLayout(self.shadow_properties_group)
        self.shadow_form_layout.setObjectName(u"shadow_form_layout")
        self.shadow_x_label = QLabel(self.shadow_properties_group)
        self.shadow_x_label.setObjectName(u"shadow_x_label")

        self.shadow_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.shadow_x_label)

        self.shadow_x_spinbox = QSpinBox(self.shadow_properties_group)
        self.shadow_x_spinbox.setObjectName(u"shadow_x_spinbox")
        self.shadow_x_spinbox.setMinimum(-20)
        self.shadow_x_spinbox.setMaximum(20)
        self.shadow_x_spinbox.setValue(1)

        self.shadow_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.shadow_x_spinbox)

        self.shadow_y_label = QLabel(self.shadow_properties_group)
        self.shadow_y_label.setObjectName(u"shadow_y_label")

        self.shadow_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.shadow_y_label)

        self.shadow_y_spinbox = QSpinBox(self.shadow_properties_group)
        self.shadow_y_spinbox.setObjectName(u"shadow_y_spinbox")
        self.shadow_y_spinbox.setMinimum(-20)
        self.shadow_y_spinbox.setMaximum(20)
        self.shadow_y_spinbox.setValue(1)

        self.shadow_form_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.shadow_y_spinbox)

        self.shadow_blur_label = QLabel(self.shadow_properties_group)
        self.shadow_blur_label.setObjectName(u"shadow_blur_label")

        self.shadow_form_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.shadow_blur_label)

        self.shadow_blur_spinbox = QSpinBox(self.shadow_properties_group)
        self.shadow_blur_spinbox.setObjectName(u"shadow_blur_spinbox")
        self.shadow_blur_spinbox.setMaximum(20)
        self.shadow_blur_spinbox.setValue(2)

        self.shadow_form_layout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.shadow_blur_spinbox)

        self.shadow_color_label = QLabel(self.shadow_properties_group)
        self.shadow_color_label.setObjectName(u"shadow_color_label")

        self.shadow_form_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.shadow_color_label)

        self.shadow_color_layout = QHBoxLayout()
        self.shadow_color_layout.setObjectName(u"shadow_color_layout")
        self.shadow_color_button = QPushButton(self.shadow_properties_group)
        self.shadow_color_button.setObjectName(u"shadow_color_button")

        self.shadow_color_layout.addWidget(self.shadow_color_button)

        self.shadow_color_preview_label = QLabel(self.shadow_properties_group)
        self.shadow_color_preview_label.setObjectName(u"shadow_color_preview_label")
        self.shadow_color_preview_label.setMinimumSize(QSize(24, 24))
        self.shadow_color_preview_label.setAutoFillBackground(True)
        self.shadow_color_preview_label.setFrameShape(QFrame.StyledPanel)

        self.shadow_color_layout.addWidget(self.shadow_color_preview_label)

        self.shadow_color_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.shadow_color_layout.addItem(self.shadow_color_spacer)


        self.shadow_form_layout.setLayout(3, QFormLayout.ItemRole.FieldRole, self.shadow_color_layout)


        self.style_form_layout.setWidget(5, QFormLayout.ItemRole.FieldRole, self.shadow_properties_group)

        self.text_outline_checkbox = QCheckBox(self.style_properties_group)
        self.text_outline_checkbox.setObjectName(u"text_outline_checkbox")

        self.style_form_layout.setWidget(6, QFormLayout.ItemRole.FieldRole, self.text_outline_checkbox)

        self.outline_properties_group = QGroupBox(self.style_properties_group)
        self.outline_properties_group.setObjectName(u"outline_properties_group")
        self.outline_properties_group.setCheckable(False)
        self.outline_form_layout = QFormLayout(self.outline_properties_group)
        self.outline_form_layout.setObjectName(u"outline_form_layout")
        self.outline_thickness_label = QLabel(self.outline_properties_group)
        self.outline_thickness_label.setObjectName(u"outline_thickness_label")

        self.outline_form_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.outline_thickness_label)

        self.outline_thickness_spinbox = QSpinBox(self.outline_properties_group)
        self.outline_thickness_spinbox.setObjectName(u"outline_thickness_spinbox")
        self.outline_thickness_spinbox.setMinimum(1)
        self.outline_thickness_spinbox.setMaximum(5)
        self.outline_thickness_spinbox.setValue(1)

        self.outline_form_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.outline_thickness_spinbox)

        self.outline_color_label = QLabel(self.outline_properties_group)
        self.outline_color_label.setObjectName(u"outline_color_label")

        self.outline_form_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.outline_color_label)

        self.outline_color_layout = QHBoxLayout()
        self.outline_color_layout.setObjectName(u"outline_color_layout")
        self.outline_color_button = QPushButton(self.outline_properties_group)
        self.outline_color_button.setObjectName(u"outline_color_button")

        self.outline_color_layout.addWidget(self.outline_color_button)

        self.outline_color_preview_label = QLabel(self.outline_properties_group)
        self.outline_color_preview_label.setObjectName(u"outline_color_preview_label")
        self.outline_color_preview_label.setMinimumSize(QSize(24, 24))
        self.outline_color_preview_label.setAutoFillBackground(True)
        self.outline_color_preview_label.setFrameShape(QFrame.StyledPanel)

        self.outline_color_layout.addWidget(self.outline_color_preview_label)

        self.outline_color_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.outline_color_layout.addItem(self.outline_color_spacer)


        self.outline_form_layout.setLayout(1, QFormLayout.ItemRole.FieldRole, self.outline_color_layout)


        self.style_form_layout.setWidget(7, QFormLayout.ItemRole.FieldRole, self.outline_properties_group)


        self.verticalLayout.addLayout(self.style_form_layout)

        self.style_preview_graphics_view = QGraphicsView(self.style_properties_group)
        self.style_preview_graphics_view.setObjectName(u"style_preview_graphics_view")
        self.style_preview_graphics_view.setMinimumSize(QSize(0, 100))

        self.verticalLayout.addWidget(self.style_preview_graphics_view)


        self.styles_tab_v_layout.addWidget(self.style_properties_group)

        self.styles_placeholder_label = QLabel(self.styles_tab)
        self.styles_placeholder_label.setObjectName(u"styles_placeholder_label")
        self.styles_placeholder_label.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.styles_placeholder_label.setWordWrap(True)

        self.styles_tab_v_layout.addWidget(self.styles_placeholder_label)

        self.styles_tab_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.styles_tab_v_layout.addItem(self.styles_tab_spacer)

        self.main_tab_widget.addTab(self.styles_tab, "")

        self.main_v_layout.addWidget(self.main_tab_widget)

        self.button_box = QDialogButtonBox(TemplateEditorWindow)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.main_v_layout.addWidget(self.button_box)


        self.retranslateUi(TemplateEditorWindow)

        self.main_tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(TemplateEditorWindow)
    # setupUi

    def retranslateUi(self, TemplateEditorWindow):
        TemplateEditorWindow.setWindowTitle(QCoreApplication.translate("TemplateEditorWindow", u"Template Editor (New Design)", None))
        self.layout_selector_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Layout:", None))
        self.add_layout_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"+", None))
        self.remove_layout_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"-", None))
        self.rename_layout_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"~", None))
        self.layout_background_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Layout Background", None))
        self.layout_bg_enable_checkbox.setText(QCoreApplication.translate("TemplateEditorWindow", u"Enable", None))
        self.layout_bg_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose Color...", None))
        self.add_textbox_to_layout_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Add Text Box", None))
        self.add_shape_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Add Shape", None))
        self.remove_selected_textbox_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Remove Selected Text Box", None))
        self.textbox_properties_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Selected Text Box Properties", None))
        self.textbox_id_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"ID/Name:", None))
        self.textbox_style_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Style:", None))
        self.label_halign.setText(QCoreApplication.translate("TemplateEditorWindow", u"H. Align:", None))
        self.label_valign.setText(QCoreApplication.translate("TemplateEditorWindow", u"V. Align:", None))
        self.layout_elements_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Layout Elements", None))
        self.shape_properties_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Selected Shape Properties", None))
        self.shape_id_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"ID/Name:", None))
        self.shape_fill_color_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Fill Color:", None))
        self.selected_shape_fill_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose...", None))
        self.shape_stroke_color_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Stroke Color:", None))
        self.selected_shape_stroke_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose...", None))
        self.shape_stroke_width_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Stroke Width:", None))
        self.main_tab_widget.setTabText(self.main_tab_widget.indexOf(self.layouts_tab), QCoreApplication.translate("TemplateEditorWindow", u"Layouts", None))
        self.style_selector_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Style:", None))
        self.add_style_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"+", None))
        self.remove_style_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"-", None))
        self.style_properties_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Style Properties", None))
        self.preview_text_input_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Preview Text:", None))
        self.font_family_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Font Family:", None))
        self.font_size_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Font Size:", None))
        self.font_color_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Font Color:", None))
        self.font_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose Color...", None))
        self.font_color_preview_label.setText("")
        self.force_caps_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Formatting:", None))
        self.force_caps_checkbox.setText(QCoreApplication.translate("TemplateEditorWindow", u"Force All Caps", None))
        self.text_shadow_checkbox.setText(QCoreApplication.translate("TemplateEditorWindow", u"Text Shadow", None))
        self.shadow_properties_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Shadow Properties", None))
        self.shadow_x_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"X Offset:", None))
        self.shadow_y_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Y Offset:", None))
        self.shadow_blur_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Blur Radius:", None))
        self.shadow_color_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Color:", None))
        self.shadow_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose...", None))
        self.text_outline_checkbox.setText(QCoreApplication.translate("TemplateEditorWindow", u"Text Outline (Basic)", None))
        self.outline_properties_group.setTitle(QCoreApplication.translate("TemplateEditorWindow", u"Outline Properties", None))
        self.outline_thickness_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Thickness:", None))
        self.outline_color_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Color:", None))
        self.outline_color_button.setText(QCoreApplication.translate("TemplateEditorWindow", u"Choose...", None))
        self.style_preview_graphics_view.setText(QCoreApplication.translate("TemplateEditorWindow", u"Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz 0123456789", None))
        self.styles_placeholder_label.setText(QCoreApplication.translate("TemplateEditorWindow", u"Style Management UI:\n"
"- List of existing Style Definitions\n"
"- Buttons: Add New Style, Edit Selected, Delete Selected\n"
"- Editing area for selected style (name, font properties, color, alignment)", None))
        self.main_tab_widget.setTabText(self.main_tab_widget.indexOf(self.styles_tab), QCoreApplication.translate("TemplateEditorWindow", u"Styles", None))
    # retranslateUi

