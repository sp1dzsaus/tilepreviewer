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
            widget = TilesetDialog(open_image(fname),
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

class TilesetOutputList(TileList):
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

def natural(n):
    n = int(n)
    if n < 1:
        raise ValueError('Natural numbers must be greater than zero.')
    return n

class LineEditPlus(QWidget):
    def __init__(self, type, labeltext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = type
        self.label = labeltext
        self.label = QLabel(labeltext, self)
        self.input = QLineEdit(self)
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        self.input.editingFinished.connect(self.checkInput)

    def checkInput(self):
        try:
            self.type(self.input.text())
        except ValueError:
            self.input.setText('')

    def getInput(self):
        return self.type(self.input.text())

class TilesetSelector(ImageView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = 1
        self.columns = 1
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

    def selectEvent(self, event):
        if self.get_rect().contains(event.pos()):
            pos = event.pos() / self.scale - self.shift
            key = (pos.x() // self.tilewidth,
                   pos.y() // self.tileheight)
            if key not in self.selected:
                self.selected.add(key)
            else:
                self.selected.remove(key)
            self.repaint()        
    
    def mousePressEvent(self, event: QMouseEvent):
        if not bool(event.modifiers() & Qt.ShiftModifier):
            super().mousePressEvent(event)
            return
        self.selectEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.selectEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not bool(event.modifiers() & Qt.ShiftModifier):
            super().mouseReleaseEvent(event)
            return

    def mouseMoveEvent(self, event: QMouseEvent):
        if not bool(event.modifiers() & Qt.ShiftModifier):
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
        for row in range(self.rows + 1):
            painter.drawLine(p(QPoint(0, row * self.tileheight)),
                             p(QPoint(self._imw, row * self.tileheight)))
        for column in range(self.columns + 1):
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

class TilesetDialog(QDialog):
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
        self.setWindowTitle('Выберете текстуру из набора')

        self.tileset = TilesetSelector(self)
        self.tileset.resize(size / 1.25)
        self.tileset.open(self.image)
        
        self.tilelist = TilesetOutputList(self.tileset, self)

        self.finish_button = QPushButton('Готово', self)
        self.finish_button.clicked.connect(self.close)

        self.rowsLabel = LineEditPlus(natural, 'Кол-во строк:     ', self)
        self.columnsLabel = LineEditPlus(natural, 'Кол-во столбцов:', self)
        self.tilewidthLabel = LineEditPlus(natural, 'Ширина тайла:', self)
        self.tileheightLabel = LineEditPlus(natural, 'Высота тайла:', self)
        self.rowsLabel.input.setText(str(1))
        self.columnsLabel.input.setText(str(1))
        self.tilewidthLabel.input.setText(str(self.tileset._imw))
        self.tileheightLabel.input.setText(str(self.tileset._imh))
        self.rowsLabel.input.editingFinished.connect(self.setRowsLabel)
        self.columnsLabel.input.editingFinished.connect(self.setColumnsLabel)
        self.tilewidthLabel.input.editingFinished.connect(self.setTileWidthLabel)
        self.tileheightLabel.input.editingFinished.connect(self.setTileHeightLabel)


        self.layout = QGridLayout(self)
        self.layout.addWidget(self.rowsLabel, 0, 0)
        self.layout.addWidget(self.columnsLabel, 1, 0)
        self.layout.addWidget(self.tilewidthLabel, 0, 1)
        self.layout.addWidget(self.tileheightLabel, 1, 1)
        self.layout.addWidget(self.tileset, 2, 0, 3, 3)
        self.layout.addWidget(self.tilelist, 2, 4, Qt.AlignLeft)
        self.layout.addWidget(self.finish_button, 3, 4, Qt.AlignLeft)

    def setRowsLabel(self):
        self.tileset.rows = self.rowsLabel.getInput()
        self.tileset.tilewidth = self.tileset._imh // self.tileset.rows
        self.tilewidthLabel.input.setText(str(self.tileset.tilewidth))
        self.tileset.repaint()

    def setColumnsLabel(self):
        self.tileset.columns = self.columnsLabel.getInput()
        self.tileset.tileheight = self.tileset._imw // self.tileset.columns
        self.tileheightLabel.input.setText(str(self.tileset.tileheight))
        self.tileset.repaint()

    def setTileWidthLabel(self):
        self.tileset.tilewidth = self.tilewidthLabel.getInput()
        self.tileset.columns = self.tileset._imw // self.tileset.tilewidth
        self.columnsLabel.input.setText(str(self.tileset.columns))
        self.tileset.repaint()

    def setTileHeightLabel(self):
        self.tileset.tileheight = self.tileheightLabel.getInput()
        self.tileset.rows = self.tileset._imh // self.tileset.tileheight
        self.rowsLabel.input.setText(str(self.tileset.rows))
        self.tileset.repaint()

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
            error.setText('Количество тайлов не должно превышать четырёх.')
            error.setWindowTitle('Ошибка')
            error.open()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec())

