from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QMouseEvent, QWheelEvent, QImage, QIcon
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRectF, QPoint, QPointF, QSize
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


class PatchworkView(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active = False
        self.scale = 1
        self.shift = QPoint(0, 0)
        self._drag_point = False
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setLineWidth(2)
        self.setMidLineWidth(1)

    #TODO: Actions
    
    def fitToHeight(self):
        self.scale = self.height() / (self.patchwork.maph * self.patchwork.tileh)

    def fitToWidth(self):
        self.scale = self.width() / (self.patchwork.mapw * self.patchwork.tilew)

    def fit(self):
        h = self.height() / (self.patchwork.maph * self.patchwork.tileh)
        w = self.width() / (self.patchwork.mapw * self.patchwork.tilew)
        self.scale = min(h, w)
        

    def resize(self, *args, **kwargs):
        super().resize(*args, **kwargs)

    def open(self, patchwork: Patchwork):
        self.active = True
        self.patchwork = patchwork
        self.image = QPixmap(patchwork.pixel_width(),
                        patchwork.pixel_height())
        patchwork.draw(QPainter(self.image))
        pixmap = QPixmap(self.image)
        self.image = pixmap.toImage()
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
        rel = event.pos() / self.scale - self.shift
        selected = self.patchwork.get_image(rel.x(), rel.y())
        def _file_location():
            path = selected._path.replace("/", "\\")
            subprocess.Popen(fr'explorer /select,"{path}"')
        _file_location()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.demo()

    def demo(self):
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt1.png'))
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt2.png'))
        self.tilelist.addTile(open_image('D:/SP1DZMAIN/PROJECTS/TilePreviewer/examples/dirt3.png'))
        self.start()

    def initUI(self):
        self.setGeometry(100, 100, 1510, 1000)
        self.setWindowTitle('TilePreviewer')
        
        self.central = QWidget(self)

        self.tilelist = TileList(self.central)

        self.start_button = QPushButton('Сгенерировать', self.central)
        self.start_button.clicked.connect(self.start)

        self.patchworkview = PatchworkView(self.central)
        #self.patchworkview.resize(1000, 900)

        self.layout = QGridLayout(self.central)
        self.layout.addWidget(self.patchworkview, 0, 1, 3, 3)
        self.layout.addWidget(self.tilelist, 0, 0, Qt.AlignLeft)
        self.layout.addWidget(self.start_button, 1, 0, Qt.AlignBottom)
        self.setCentralWidget(self.central)


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

