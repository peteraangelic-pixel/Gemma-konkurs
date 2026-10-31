"""Infer a copy task from repeated tiled panels and matching central stamps.

No game IDs, fixed palette/positions, solution paths, or environment state.
Uses only pixels; an observed transition must agree with the chosen cell's
predicted target color before the policy continues. Otherwise it yields.
"""
from collections import Counter
import numpy as np


def rectangles(grid):
    a=np.asarray(grid,dtype=np.uint8)
    active={};out=[]
    for y,row in enumerate(a):
        starts=np.r_[0,np.flatnonzero(row[1:]!=row[:-1])+1]
        ends=np.r_[starts[1:],len(row)]
        current={(int(row[x]),int(x),int(end)):y for x,end in zip(starts,ends)}
        for key,top in active.items():
            if key not in current:
                color,left,right=key;out.append((top,y,left,right,color))
        active={key:active.get(key,y) for key in current}
    for (color,left,right),top in active.items():out.append((top,len(a),left,right,color))
    return out


def infer_copy_action(grid,learned=None,extract_rectangles=rectangles):
    a=np.asarray(grid,dtype=np.uint8)
    squares=[r for r in extract_rectangles(a) if r[1]-r[0]==r[3]-r[2] and r[1]-r[0]>=3]
    sizes=Counter(r[1]-r[0] for r in squares)
    sizes=[s for s,n in sizes.items() if n>=8]
    if not sizes:return None
    size=max(sizes,key=lambda s:s*s*sum(r[1]-r[0]==s for r in squares))
    cells={(r[0],r[2]):r[4] for r in squares if r[1]-r[0]==size}
    gaps=Counter()
    for y,x in cells:
        for yy,xx in cells:
            if y==yy and size<xx-x<=3*size:gaps[xx-x]+=1
    if not gaps:return None
    pitch=max(gaps,key=gaps.get)
    origins={(y-i*pitch,x-j*pitch) for y,x in cells for i in range(3) for j in range(3)}
    panels=[]
    background=int(np.bincount(a.ravel(),minlength=256).argmax())
    span=2*pitch+size
    for y,x in sorted(origins):
        if y<0 or x<0 or y+span>len(a) or x+span>a.shape[1]:continue
        coords=[(i,j) for i in range(3) for j in range(3) if (i,j)!=(1,1)]
        if not all((y+i*pitch,x+j*pitch) in cells for i,j in coords):continue
        if (y+pitch,x+pitch) in cells:continue
        stamp=a[y+pitch:y+pitch+size,x+pitch:x+pitch+size].tobytes()
        margin=max(1,pitch-size)*2
        top=max(0,y-margin);bottom=min(len(a),y+span+margin)
        left=max(0,x-margin);right=min(a.shape[1],x+span+margin)
        ring=a[top:bottom,left:right].copy()
        ring[y-top:y-top+span,x-left:x-left+span]=background
        border=int(np.count_nonzero(ring!=background))
        panels.append({'y':y,'x':x,'stamp':stamp,'border':border,'coords':coords})
    if learned and size%3==0 and panels:
        sub=size//3;constraints={};valid=True
        palette=learned['colors'];center_symbols=learned['center_symbols']
        domain={cells[(p['y']+i*pitch,p['x']+j*pitch)] for p in panels for i,j in p['coords']}
        domain.update(int(a[p['y']+pitch+size//2,p['x']+pitch+size//2]) for p in panels)
        if len(domain)!=2:return None
        for panel in panels:
            for i,j in panel['coords']:
                patch=a[panel['y']+pitch+i*sub:panel['y']+pitch+(i+1)*sub,
                        panel['x']+pitch+j*sub:panel['x']+pitch+(j+1)*sub]
                symbol=int(patch[0,0]);position=(panel['y']+i*pitch,panel['x']+j*pitch)
                if symbol not in palette or not np.all(patch==symbol):valid=False;break
                center=int(a[panel['y']+pitch+size//2,panel['x']+pitch+size//2])
                value=center if symbol in center_symbols else next(v for v in domain if v!=center)
                if position in constraints and constraints[position]!=value:valid=False;break
                constraints[position]=value
            if not valid:break
        if valid:
            for (y,x),value in sorted(constraints.items()):
                if cells[(y,x)]!=value:
                    return (6,x+size//2,y+size//2),{'row':y+size//2,'col':x+size//2,
                        'expected_color':value,'panels':len(panels),'model':learned}
    choices=[]
    for target in panels:
        refs=[p for p in panels if p is not target and p['stamp']==target['stamp']]
        if len(refs)!=1 or target['border']<=refs[0]['border']:continue
        ref=refs[0]
        for i,j in target['coords']:
            expected=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]
            actual=cells[(target['y']+i*pitch,target['x']+j*pitch)]
            if actual!=expected:
                choices.append((target['border']-ref['border'],target['y']+i*pitch+size//2,
                                target['x']+j*pitch+size//2,expected,None))
                break
    # If stamps differ, infer their symbolic color-to-tile rule from all the
    # completed reference panels. Require perfect agreement, not a palette
    # assumption (e.g. white/red). The outlined panel supplies a new query.
    if not choices and size%3==0:
        sub=size//3
        for target in panels:
            refs=[p for p in panels if p is not target]
            if len(refs)<2 or target['border']<=max(p['border'] for p in refs):continue
            mapping={};valid=True
            for ref in refs:
                for i,j in ref['coords']:
                    patch=a[ref['y']+pitch+i*sub:ref['y']+pitch+(i+1)*sub,
                            ref['x']+pitch+j*sub:ref['x']+pitch+(j+1)*sub]
                    symbol=int(patch[0,0])
                    value=cells[(ref['y']+i*pitch,ref['x']+j*pitch)]
                    if not np.all(patch==symbol) or (symbol in mapping and mapping[symbol]!=value):valid=False;break
                    mapping[symbol]=value
                if not valid:break
            if not valid or len(mapping)<2 or len(set(mapping.values()))<2:continue
            for i,j in target['coords']:
                patch=a[target['y']+pitch+i*sub:target['y']+pitch+(i+1)*sub,
                        target['x']+pitch+j*sub:target['x']+pitch+(j+1)*sub]
                symbol=int(patch[0,0])
                if symbol not in mapping or not np.all(patch==symbol):valid=False;break
                expected=mapping[symbol]
                actual=cells[(target['y']+i*pitch,target['x']+j*pitch)]
                if actual!=expected:
                    center=int(a[refs[0]['y']+pitch+size//2,refs[0]['x']+pitch+size//2])
                    model={'colors':dict(mapping),'center_symbols':[k for k,v in mapping.items() if v==center]}
                    choices.append((target['border']-max(p['border'] for p in refs),
                                    target['y']+i*pitch+size//2,target['x']+j*pitch+size//2,expected,model))
                    break
    if not choices:return None
    _,y,x,color,model=max(choices,key=lambda c:c[:4])
    return (6,x,y),{'row':y,'col':x,'expected_color':color,'panels':len(panels),'model':model}


class TemplateTransfer:
    def __init__(self,extract_rectangles=rectangles):
        self.extract_rectangles=extract_rectangles
        self.prediction=None
        self.level=None
        self.rejected=False
        self.hits=0
        self.mismatches=0
        self.learned=None

    def act(self,grid,available,level):
        a=np.asarray(grid,dtype=np.uint8)
        if level!=self.level:
            self.prediction=None;self.rejected=False;self.level=level
        if self.prediction is not None:
            p=self.prediction
            if int(a[p['row'],p['col']])!=p['expected_color']:
                self.rejected=True;self.mismatches+=1;self.learned=None
            self.prediction=None
        if 6 in available and not self.rejected:
            result=infer_copy_action(a,self.learned,self.extract_rectangles)
            if result:
                action,self.prediction=result;self.hits+=1
                if self.prediction.get('model'):self.learned=self.prediction['model']
                return action
        return None
