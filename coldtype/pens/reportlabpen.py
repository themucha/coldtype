from fontTools.pens.reportLabPen import ReportLabPen as FTReportLabPen
from reportlab.graphics import renderPM, renderPDF
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import Group, Drawing, scale

if __name__ == "__main__":    
    import os
    import sys
    dirname = os.path.realpath(os.path.dirname(__file__))
    sys.path.append(f"{dirname}/../..")

from coldtype.geometry import Rect, Edge, Point
from coldtype.pens.drawablepen import DrawablePenMixin, Gradient

class ReportLabPen(DrawablePenMixin, FTReportLabPen):
    def __init__(self, dat):
        super().__init__(None, path=None)
        self.dat = dat
        self.dat.replay(self)

        for attr in self.dat.attrs.items():
            self.applyDATAttribute(attr)
    
    def fill(self, color):
        self.path.fillColor = HexColor(color.html)

if __name__ == "__main__":
    sys.path.insert(0, os.path.realpath("."))
    from coldtype.pens.datpen import DATPen
    from coldtype.viewer import previewer

    with previewer() as p:
        r = Rect((0, 0, 1000, 1000))
        dp1 = DATPen(fill="random")
        dp1.oval(r.inset(200, 200))
        rp = ReportLabPen(dp1)
        #p.send(SVGPen.Composite([dp1, dp], r), rect=r)
        g = Group(rp.path)
        #g.translate(0, 200)
        #g.scale(0.3, 0.3)
        d = Drawing(r.w, r.h)
        d.add(rp.path)

        renderPDF.drawToFile(d, "test.pdf")