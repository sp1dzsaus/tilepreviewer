from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QMouseEvent, QWheelEvent, QImage, QIcon, QClipboard, QPen
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize
import sys
from patchwork import Patchwork, InvalidTileData
import subprocess

def open_image(path):
    image = QImage(path)
    image._path = path
    return image

class DeselectableQListWidget(QListWidget):
    def mousePressEvent(self, *args, **kwargs):
        prev = self.selectedItems()
        super().mousePressEvent(*args, **kwargs)
        if self.selectedItems() == prev:
            self.clearSelection()
            if hasattr(self, 'deselectEvent'):
                self.deselectEvent()

    def clearSelection(self, *args, **kwargs):
        super().clearSelection(*args, **kwargs)
        self.deselectEvent()

class TileList(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.listwidget = DeselectableQListWidget()
        self.listwidget.setIconSize(QSize(70, 70))
        self.listwidget.deselectEvent = self.disable_item_interaction_panel
        self.listwidget.itemSelectionChanged.connect(self.enable_item_interaction_panel)
        layout.addWidget(self.listwidget)
        
        self.delete_button = QPushButton('Удалить элемент', self)
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_items)
        layout.addWidget(self.delete_button)
        
        self.open_button = QPushButton('Добавить элемент', self)
        self.open_button.clicked.connect(self.openTileSelection)
        layout.addWidget(self.open_button)
        
        self.setLayout(layout)

    def enable_item_interaction_panel(self):
        self.delete_button.setEnabled(True)

    def disable_item_interaction_panel(self):
        self.delete_button.setEnabled(False)

    def openTileSelection(self):
        fname = QFileDialog.getOpenFileName(self, 'Выбрать текстуру', '',
                                            'Изображение (*.png *.jpg *.bmp)')[0]
        if fname:
            self.addTile(open_image(fname))

    def delete_items(self):
        for item in self.listwidget.selectedItems():
            self.listwidget.takeItem(self.listwidget.row(item))
        self.listwidget.clearSelection()

    def addTile(self, image: QImage):
        new = QListWidgetItem(self.listwidget)
        new.setIcon(QIcon(QPixmap.fromImage(image).scaled(100, 100)))
        new.setText(image._path[image._path.rfind('/') + 1:])
        new.__data = image

    def getData(self):
        return [self.listwidget.item(x).__data
                for x in range(self.listwidget.count())]


class ImageView(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active = False
        self.scale = 1
        self.shift = QPoint(0, 0)
        self._drag_point = False
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setLineWidth(2)
        self.setMidLineWidth(1)

    def fitToHeight(self):
        self.scale = self.height() / self._imh

    def fitToWidth(self):
        self.scale = self.width() / self._imw

    def fit(self):
        h = self.height() / self._imh
        w = self.width() / self._imw
        self.scale = min(h, w)

    def open(self, image: QImage):
        self.active = True
        self.image = image
        self._imw = self.image.width()
        self._imh = self.image.height()
        self.fit()
        self.repaint()

    def paintEvent(self, e):
        if self.active:
            painter = QPainter(self)
            painter.drawImage(self.get_rect(), self.image)
        super().paintEvent(e)

    def get_rect(self):
        return QRectF(self.scale * (self.shift.x()),
                      self.scale * (self.shift.y()),
                      self.scale * self._imw,
                      self.scale * self._imh)

    def mousePressEvent(self, event: QMouseEvent):
        self._drag_point = event.pos() / self.scale       

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_point = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_point:
            pos = event.pos() / self.scale
            delta = (pos - self._drag_point)
            self.shift += delta
            self._drag_point = pos
            self.repaint()
            
    def wheelEvent(self, event: QWheelEvent):
        mod = (2 ** (event.angleDelta().y() // 120) - 1) / 6          
        self.scale *= mod + 1            
        self.repaint()

    def contextMenuEvent(self, event):
        def _copy():
            QApplication.clipboard().setImage(self.image)
        menu = QMenu(self)
        action1 = QAction('Копировать')
        action1.triggered.connect(_copy)
        menu.addAction(action1)

        menu.exec(event.globalPos())

        
class PatchworkView(ImageView):
    def open(self, patchwork: Patchwork):
        self.active = True
        self.patchwork = patchwork
        self.image = QPixmap(patchwork.pixel_width(),
                        patchwork.pixel_height())
        patchwork.draw(QPainter(self.image))
        self.image = self.image.toImage()
        self._imw = self.image.width()
        self._imh = self.image.height()
        self.fit()
        self.repaint()

    def contextMenuEvent(self, event):
        rel = event.pos() / self.scale - self.shift
        selected = self.patchwork.get_image(rel.x(), rel.y())
        def _file_location():
            path = selected._path.replace("/", "\\")
            subprocess.Popen(fr'explorer /select,"{path}"')
        def _copy():
            QApplication.clipboard().setImage(self.image)
        menu = QMenu(self)
        action1 = QAction('Копировать')
        action1.triggered.connect(_copy)
        menu.addAction(action1)
        action2 = QAction('Перейти к расположению тайла')
        action2.triggered.connect(_file_location)
        if not self.get_rect().contains(event.pos()):
            action2.setDisabled(True)
        menu.addAction(action2)
        menu.exec(event.globalPos())


class TilemapSlicerView(ImageView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selection = QRect(0, 0, 0, 0)
        self._select_point = False
        self.shift = QPoint(5, 5)

    def x_clamp(self, x):
        rect = self.get_rect()
        return min(rect.width() + rect.x(), max(rect.x(), x))

    def y_clamp(self, y):
        rect = self.get_rect()
        return min(rect.height() + rect.y(), max(rect.y(), y))
    
    def mousePressEvent(self, event: QMouseEvent):
        self.selection = QRect(0, 0, 0, 0)
        self._select_point = QPointF(self.x_clamp(round(event.x())) / self.scale,
                                     self.y_clamp(round(event.y())) / self.scale)
        self.selection.setX(self._select_point.x())
        self.selection.setY(self._select_point.y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._select_point = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._select_point:
            pos = QPointF(self.x_clamp(round(event.x())) / self.scale,
                          self.y_clamp(round(event.y())) / self.scale)
            delta = (pos - self._select_point)
            self.selection.setSize(QSize(delta.x(), delta.y()))
            self.repaint()

    def get_selection_rect(self):
        return QRectF(self.selection.x() * self.scale,
                      self.selection.y() * self.scale,
                      self.selection.width() * self.scale,
                      self.selection.height() * self.scale)

    def isSelectionSquare(self):
        return abs(self.selection.width()) == abs(self.selection.height())
    
    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        try:
            painter.setPen(QPen(Qt.green if self.isSelectionSquare() else Qt.blue, 
                                3, Qt.DashDotLine, Qt.RoundCap, Qt.RoundJoin))
        except Exception as e:
            print(e)
        painter.drawRect(self.get_selection_rect())

class TilemapSlicerDialog(QDialog):
    def __init__(self, image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = image
        self.initUI()

    def initUI(self):
        geometry = self.parentWidget().geometry()
        size = geometry.size() / 2
        geometry.setSize(size)
        geometry.translate(size.width() / 2, size.height() / 2)
        self.setGeometry(geometry)
        self.setWindowTitle('Вырезать текстуру из набора')

        self.slicer = TilemapSlicerView(self)
        self.slicer.resize(size / 1.25)
        self.slicer.open(self.image)
        self.layout = QGridLayout(self)
        self.layout.addWidget(self.slicer, 0, 0, 3, 3)




class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.demo()

    def demo(self):
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt/dirt1.png'))
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt/dirt2.png'))
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt/dirt3.png'))
        self.start()

    def initUI(self):
        self.setGeometry(100, 100, 1510, 1000)
        self.setWindowTitle('TilePreviewer')
        
        self.central = QWidget(self)

        self.tilelist = TileList(self.central)

        self.start_button = QPushButton('Сгенерировать', self.central)
        self.start_button.clicked.connect(self.start)

        self.patchworkview = PatchworkView(self.central)
        self.patchworkview.resize(1000, 900)

        self.layout = QGridLayout(self.central)
        self.layout.addWidget(self.patchworkview, 0, 1, 3, 3)
        self.layout.addWidget(self.tilelist, 0, 0, Qt.AlignLeft)
        self.layout.addWidget(self.start_button, 1, 0, 1, 1, Qt.AlignBottom)
        self.setCentralWidget(self.central)

        widget = TilemapSlicerDialog(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/nodes/chaotic.bmp'),
                                     self)
        widget.show()


    def start(self):
        try:
            data = self.tilelist.getData()
            patchwork = Patchwork(*self.tilelist.getData())
            self.patchworkview.open(patchwork)
        except InvalidTileData as ex:
            error = QMessageBox(self)
            error.setText('Ошибка: ' + str(ex))
            error.setWindowTitle('Ошибка')
            error.open()
        except NotImplementedError as ex:
            error = QMessageBox(self)
            error.setText('Эта функция не доступна в данной версии приложения.')
            error.setWindowTitle('Ошибка')
            error.open()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec())

