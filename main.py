from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QMouseEvent, QWheelEvent, QImage, QIcon, QClipboard, QPen
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize
import sys
from patchwork import Patchwork, InvalidTileData
import subprocess
from math import ceil

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
            widget = TilesetSlicerDialog(open_image(fname),
                                         self,
                                         self.window())
            widget.show()

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

class SlicerProductList(TileList):
    def __init__(self, slicer, *args, **kwargs):
        self.slicer = slicer
        super().__init__(*args, **kwargs)
    
    def openTileSelection(self):
        if self.slicer.isAnythingSelected():
            for selection in self.slicer.selectedTiles():
                self.addTile(selection)
        self.slicer.retireSelection()
        self.slicer.repaint()

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

    def imToCanCoords(self, point):
        return (point + self.shift) * self.scale

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

    def convertRect(self, rect):
        return QRectF(self.scale * (rect.x() + self.shift.x()),
                      self.scale * (rect.y() + self.shift.y()),
                      self.scale * rect.width(),
                      self.scale * rect.height())
    
    def get_rect(self):
        return self.convertRect(QRectF(0,
                                       0,
                                       self._imw,
                                       self._imh))

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


class TilesetSlicerView(ImageView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selection = QRect(0, 0, 0, 0)
        self._select_point = False
        self.shift = QPoint(5, 5)
        self.gray_areas = []

    def retireSelection(self):
        self.gray_areas.append(self.selection)
        self.selection = QRect(0, 0, 0, 0)
        self.repaint()

    def x_clamp(self, x):
        rect = self.get_rect()
        return min(rect.width() + rect.x(), max(rect.x(), x))

    def y_clamp(self, y):
        rect = self.get_rect()
        return min(rect.height() + rect.y(), max(rect.y(), y))
    
    def mousePressEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mousePressEvent(event)
            return
        self.selection = QRect(0, 0, 0, 0)
        pos = event.pos()
        self._select_point = QPointF(self.x_clamp(int(pos.x())) / self.scale - self.shift.x(),
                                     self.y_clamp(int(pos.y())) / self.scale - self.shift.y())
        self.selection.setX(self._select_point.x())
        self.selection.setY(self._select_point.y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mouseReleaseEvent(event)
            return
        self._select_point = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mouseMoveEvent(event)
            return        
        if self._select_point:
            pos = event.pos()
            pos.setX(pos.x() + self.scale)
            pos.setY(pos.y() + self.scale)
            pos = QPointF(self.x_clamp(ceil(pos.x())) / self.scale - self.shift.x(),
                          self.y_clamp(ceil(pos.y())) / self.scale - self.shift.y())
            delta = (pos - self._select_point)
            self.selection.setSize(QSize(delta.x(), delta.y()))
            self.repaint()

    def get_selection_rect(self):
        return self.convertRect(self.selection)

    def isSelectionSquare(self):
        return abs(self.selection.width()) == abs(self.selection.height())

    def isAnythingSelected(self):
        return self.selection.width() != 0 and self.selection.height() != 0

    def selectedArea(self):
        rect = QRect(self.selection.x(),
                     self.selection.y(),
                     self.selection.width(),
                     self.selection.height())
        if rect.width() < 0:
            rect.translate(rect.width(), 0)
            rect.setWidth(abs(rect.width()))
        if rect.height() < 0:
            rect.translate(0, rect.height())
            rect.setHeight(abs(rect.height()))
        cropped = self.image.copy(rect)
        cropped._path = self.image._path
        return cropped
    
    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.green if self.isSelectionSquare() else Qt.blue,
                            3, Qt.DashDotLine, Qt.RoundCap, Qt.RoundJoin))
        for area in self.gray_areas:
            painter.fillRect(self.convertRect(area), QColor(150, 150, 150, 150))
        painter.drawRect(self.get_selection_rect())


class TilesetTableView(ImageView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = 14
        self.columns = 14
        self.tilewidth = 0
        self.tileheight = 0
        self.shift = QPoint(5, 5)
        self.selected = set()

    def retireSelection(self):
        self.selected.clear()

    def open(self, *args, **kwargs):
        super().open(*args, **kwargs)
        self.tilewidth = self._imw // self.columns
        self.tileheight = self._imh // self.rows
    
    def mousePressEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mousePressEvent(event)
            return
        pos = event.pos() / self.scale - self.shift
        self.selected.add((pos.x() // self.tilewidth,
                           pos.y() // self.tileheight))
        self.repaint()


    def mouseReleaseEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mouseReleaseEvent(event)
            return

    def mouseMoveEvent(self, event: QMouseEvent):
        if bool(event.modifiers() & Qt.ShiftModifier):
            super().mouseMoveEvent(event)
            return

    def isAnythingSelected(self):
        return bool(self.selected)

    def selectedTiles(self):
        out = []
        for selection in self.selected:
            x, y = selection
            rect = QRect(x * self.tilewidth,
                         y * self.tileheight,
                         self.tilewidth,
                         self.tileheight)
            cropped = self.image.copy(rect)
            cropped._path = self.image._path
            out.append(cropped)
        return out
    
    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        pen = QPen(Qt.white, 3, Qt.SolidLine, Qt.SquareCap, Qt.RoundJoin)
        painter.setPen(pen)
        p = self.imToCanCoords
        for row in range(self.rows):
            painter.drawLine(p(QPoint(0, row * self.tileheight)),
                             p(QPoint(self._imw, row * self.tileheight)))
        for column in range(self.columns):
            painter.drawLine(p(QPoint(column * self.tilewidth, 0)),
                             p(QPoint(column * self.tilewidth, self._imh)))
        pen = QPen(Qt.black, 3, Qt.DashLine, Qt.SquareCap, Qt.RoundJoin)
        painter.setPen(pen)
        for selection in self.selected:
            x, y = selection
            painter.fillRect(QRect(p(QPoint(x * self.tilewidth,
                                            y * self.tileheight)),
                                   QSize(self.tilewidth * self.scale,
                                         self.tileheight * self.scale)),
                             QColor(190, 200, 255, 70))
            painter.drawRect(QRect(p(QPoint(x * self.tilewidth,
                                            y * self.tileheight)),
                                   QSize(self.tilewidth * self.scale,
                                         self.tileheight * self.scale)))            

class TilesetSlicerDialog(QDialog):
    def __init__(self, image, tilelist, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = image
        self.resulttilelist = tilelist
        self.initUI()
        self.finished.connect(self.finish)

    def initUI(self):
        geometry = self.parentWidget().geometry()
        size = geometry.size() / 2
        geometry.setSize(size)
        geometry.translate(size.width() / 2, size.height() / 2)
        self.setGeometry(geometry)
        self.setWindowTitle('Вырезать текстуру из набора')

        self.tileset = TilesetTableView(self)
        self.tileset.resize(size / 1.25)
        self.tileset.open(self.image)
        
        self.tilelist = SlicerProductList(self.tileset, self)

        self.finish_button = QPushButton('Готово', self)
        self.finish_button.clicked.connect(self.close)
        
        self.layout = QGridLayout(self)
        self.layout.addWidget(self.tileset, 0, 0, 3, 3)
        self.layout.addWidget(self.tilelist, 0, 4, Qt.AlignLeft)
        self.layout.addWidget(self.finish_button, 1, 4, Qt.AlignLeft)

    def finish(self):
        for image in self.tilelist.getData():
            self.resulttilelist.addTile(image)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

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

