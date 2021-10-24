class InvalidTileData(Exception):
    pass

class Patchwork:
    def __init__(self, *images):
        if not images:
            raise InvalidTileData('No tiles given.')
        self.map = Patchwork._gen(len(images))
        if self.map is NotImplemented:
            raise NotImplementedError
        if len(set([(image.width(),
                     image.height()) for image in images])) != 1:
            raise InvalidTileData('Tile sizes must be identical.')
        sample = images[0]
        self.tilew = sample.width()
        self.tileh = sample.height()
        self.maph, self.mapw = len(self.map), len(self.map[0])
        self.images = images
    
    def draw(self, painter):
        for y in range(self.maph + 1):
            for x in range(self.mapw + 1):
                ind = self.map[y % self.maph][x % self.mapw]
                painter.drawImage((x - 0.5) * self.tilew,
                                  (y - 0.5) * self.tileh,
                                  self.images[ind])
    
    def get_image(self, x, y):
        x = int((x) / self.tilew + 0.5)
        y = int((y) / self.tileh + 0.5)
        return self.images[self.map[y % self.maph][x % self.mapw]]
    
    def pixel_width(self):
        return self.mapw * self.tilew
    
    def pixel_height(self):
        return self.maph * self.tileh    
    
    @classmethod
    def _gen(cls, n) -> list:
        if n == 1:
            return [[0]]
        elif n == 2:
            return [[1, 0, 0, 0],
                    [1, 1, 1, 0],
                    [1, 1, 0, 1],
                    [0, 1, 0, 0]]
        elif n == 3:
            return [[0, 0, 0, 0, 0, 1, 1, 2, 2],
                    [0, 0, 2, 1, 0, 2, 2, 1, 1],
                    [1, 2, 1, 2, 0, 1, 2, 1, 2],
                    [2, 0, 0, 1, 1, 1, 1, 1, 2],
                    [0, 2, 2, 1, 1, 0, 2, 1, 0],
                    [0, 2, 0, 2, 0, 2, 0, 1, 2],
                    [2, 2, 0, 0, 1, 1, 2, 2, 2],
                    [0, 2, 1, 1, 0, 0, 2, 2, 1],
                    [1, 2, 0, 1, 0, 1, 0, 1 ,0]]
        elif n == 4:
            return [[1, 0, 0, 0, 1, 0, 2, 0, 1, 0, 0, 0, 1, 0, 2, 0],
                    [1, 1, 1, 0, 2, 0, 2, 3, 3, 3, 3, 2, 0, 2, 0, 1],
                    [1, 1, 0, 1, 3, 3, 2, 3, 1, 1, 0, 1, 3, 3, 2, 3],
                    [0, 1, 0, 0, 1, 2, 1, 3, 2, 3, 2, 2, 3, 0, 3, 1],
                    [2, 1, 3, 1, 2, 1, 1, 1, 2, 1, 3, 1, 2, 1, 1, 1],
                    [1, 3, 1, 2, 2, 2, 2, 1, 3, 1, 3, 0, 0, 0, 0, 3],
                    [0, 0, 3, 0, 2, 2, 1, 2, 0, 0, 3, 0, 2, 2, 1, 2],
                    [0, 1, 0, 2, 1, 2, 1, 1, 2, 3, 2, 0, 3, 0, 3, 3],
                    [3, 2, 2, 2, 3, 2, 0, 2, 3, 2, 2, 2, 3, 2, 0, 2],
                    [1, 1, 1, 0, 2, 0, 2, 3, 3, 3, 3, 2, 0, 2, 0, 1],
                    [3, 3, 2, 3, 1, 1, 0, 1, 3, 3, 2, 3, 1, 1, 0, 1],
                    [0, 1, 0, 0, 1, 2, 1, 3, 2, 3, 2, 2, 3, 0, 3, 1],
                    [0, 3, 1, 3, 0, 3, 3, 3, 0, 3, 1, 3, 0, 3, 3, 3],
                    [1, 3, 1, 2, 2, 2, 2, 1, 3, 1, 3, 0, 0, 0, 0, 3],
                    [2, 2, 1, 2, 0, 0, 3, 0, 2, 2, 1, 2, 0, 0, 3, 0],
                    [0, 1, 0, 2, 1, 2, 1, 1, 2, 3, 2, 0, 3, 0, 3, 3]]
