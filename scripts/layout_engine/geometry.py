"""Small, deterministic geometry primitives. Coordinates are raw units, Y up."""
from math import hypot

EPS=1e-6
DIRS=((1,0),(0,1),(-1,0),(0,-1))

def point(p):return (round(p[0],6),round(p[1],6))
def box(v):return (v['minX'],v['minY'],v['maxX'],v['maxY'])
def asbox(b):return dict(zip(('minX','minY','maxX','maxY'),b))
def shift(b,dx,dy):return (b[0]+dx,b[1]+dy,b[2]+dx,b[3]+dy)
def grow(b,d):return (b[0]-d,b[1]-d,b[2]+d,b[3]+d)
def overlap(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def inside(p,b):return b[0]-EPS<=p[0]<=b[2]+EPS and b[1]-EPS<=p[1]<=b[3]+EPS
def manhattan(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])
def seg_box(a,b,r):
    if abs(a[1]-b[1])<EPS:return r[1]-EPS<=a[1]<=r[3]+EPS and max(min(a[0],b[0]),r[0])<=min(max(a[0],b[0]),r[2])+EPS
    if abs(a[0]-b[0])<EPS:return r[0]-EPS<=a[0]<=r[2]+EPS and max(min(a[1],b[1]),r[1])<=min(max(a[1],b[1]),r[3])+EPS
    raise ValueError('non-orthogonal segment')
def onseg(p,a,b):
    return abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<EPS and min(a[0],b[0])-EPS<=p[0]<=max(a[0],b[0])+EPS and min(a[1],b[1])-EPS<=p[1]<=max(a[1],b[1])+EPS
def intersection(a,b,c,d):
    """Returns point, ('overlap',), or None; no connectivity decision here."""
    ah=abs(a[1]-b[1])<EPS;ch=abs(c[1]-d[1])<EPS
    if ah!=ch:
        p=(c[0],a[1]) if ah else (a[0],c[1])
        return p if onseg(p,a,b) and onseg(p,c,d) else None
    if (ah and abs(a[1]-c[1])>EPS) or (not ah and abs(a[0]-c[0])>EPS):return None
    axis=0 if ah else 1
    lo=max(min(a[axis],b[axis]),min(c[axis],d[axis]));hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
    if hi<lo-EPS:return None
    if hi>lo+EPS:return ('overlap',)
    return (lo,a[1]) if ah else (a[0],lo)
def compact(path):
    out=[]
    for p in path:
        p=point(p)
        if out and p==out[-1]:continue
        while len(out)>1 and ((out[-1][0]==out[-2][0]==p[0]) or (out[-1][1]==out[-2][1]==p[1])):out.pop()
        out.append(p)
    return out
def gridpoints(a,b,step=5):
    n=int(round(manhattan(a,b)/step))
    if n==0:return [point(a)]
    return [point((a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n)) for i in range(n+1)]
def unionbox(boxes):
    return (min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))

def rotate(p,degrees,origin=(0,0)):
    # Only exact quarter turns are admitted; keep physical pins on the grid.
    x,y=p[0]-origin[0],p[1]-origin[1]
    for _ in range((int(degrees)//90)%4):x,y=-y,x
    return point((x+origin[0],y+origin[1]))

def rotate_box(b,degrees,origin=(0,0)):
    ps=[rotate(p,degrees,origin) for p in ((b[0],b[1]),(b[0],b[3]),(b[2],b[1]),(b[2],b[3]))]
    return unionbox([(x,y,x,y) for x,y in ps])

def ground_box(marker):
    x,y=marker['point']
    if marker.get('nativeGlyph'):return rotate_box((x-10.5,y-19.5,x+10.5,y-9.5),marker.get('rotation',0),(x,y))
    return rotate_box((x-7,y-10,x+7,y-4),marker.get('rotation',0),(x,y))
