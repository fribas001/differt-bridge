"""Measured side-by-side fields versus an independent Maxwell BIE reference."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

W,H,FPS=1600,900,24
BG='#08111c';PANEL='#102334';TEXT='#eff5fa';MUTED='#9fb3c5';GRID='#294254';WHITE='#ffffff'
COLORS={'sionna':'#f4aa52','differt':'#48d3e2'}
CHAPTERS=[(0,'Native engines','concrete_Ez',0,'native'),(10,'Reciprocal profile','concrete_Ez',0,'reciprocal'),(20,'Horizontal polarization','concrete_Hz',4,'reciprocal'),(30,'New low-permittivity material','holdout_low_Hz',4,'reciprocal'),(40,'New high-permittivity material','holdout_high_Hz',4,'reciprocal'),(50,'Remaining Maxwell error','concrete_Hz',4,'reciprocal')]

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def z(v):a=np.asarray(v);return a[...,0]+1j*a[...,1]
def font(size,bold=False):return ImageFont.truetype('C:/Windows/Fonts/'+('segoeuib.ttf' if bold else 'segoeui.ttf'),size)
F={s:font(s) for s in (17,19,20,22,24,28,32,38,44)};B={s:font(s,True) for s in (20,24,28,32,38,44)}

class Renderer:
    def __init__(self,root):
        self.root=root;self.data=read(root/'work/diffraction-model-errors/analysis.json')
        self.groups={(r['profile'],r['name']):r for r in self.data['sweep']}
        self.cases={c['name']:c for c in read(root/'work/mer/cases.json')['cases']}
        self.raw={}
        for engine in COLORS:
            for profile in ('native','reciprocal'):
                path=root/f'work/mer/{engine}-{profile}/{engine}_float32.json'
                self.raw[engine,profile]={r['name']:r for r in read(path)['cases']}
    def render(self,frame):
        t=(frame-1)/FPS;ch=min(int(t//10),5);start,title,name,source,profile=CHAPTERS[ch];j=min(52,int((t-start)/10*53));angle=5+5*j
        im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,color=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=color)
        text(40,24,'Diffraction against Maxwell',44,bold=True)
        text(40,83,'Same wedge, ports, material and scale  |  Actual engine paths  |  Independent BIE field',24,MUTED)
        text(1130,34,f'{ch+1:02d} / 06   •   {t:04.1f} s',28,MUTED)
        if ch<5:
            label=f'{title}  •  {name.replace("_"," / ")}  •  receiver {angle:03d}°'
        else:label='Consistency improved; finite-distance dielectric UTD remains an approximation'
        text(40,117,label,22,WHITE)
        for engine,x in [('sionna',40),('differt',820)]:
            color=COLORS[engine];r=self.groups[engine+'-'+profile,name];entries=[e for e in r['entries'] if e['source']==source]
            values=z([e['prediction'] for e in entries]);reference=z([e['reference'] for e in entries]);u,ref=values[j],reference[j]
            d.rounded_rectangle((x,157,x+740,811),radius=18,fill=PANEL)
            text(x+24,174,'Sionna RT' if engine=='sionna' else 'DiffeRT',32,color,True)
            text(x+24,218,profile+' profile',20,MUTED)
            text(x+340,179,f'{100*r["total_complex_rms"]:.2f}%',38,color,True)
            text(x+485,193,'total complex RMS error',19,MUTED)
            if ch==5:
                text(x+28,266,'Error decreases with electrical distance',24,bold=True)
                text(x+28,305,'Concrete / Hz • float64 formula control',20,MUTED)
                rows=sorted([a for a in self.data['distance'] if a['name']=='concrete_Hz'],key=lambda a:a['scale'])
                for k,row in enumerate(rows):
                    yy=365+k*78;v=100*row['total_complex_rms'];text(x+28,yy,f'{row["scale"]}× distance',22)
                    d.rounded_rectangle((x+180,yy,x+180+v*65,yy+34),8,fill=color);text(x+195+v*65,yy,f'{v:.2f}%',22)
                text(x+28,626,'The engines agree after correction.',24,bold=True)
                text(x+28,666,'Agreement does not imply Maxwell accuracy.',24)
                text(x+28,714,'No new heuristic physics patch was installed.',20,MUTED)
                text(x+28,751,'2D solid lossy wedge; no general 3D certification.',20,MUTED)
                continue
            # Identical top-down geometry, in wavelength units.
            cx,cy=x+164,414;scale=29
            def point(q):return (cx+float(q[0])*scale,cy-float(q[1])*scale)
            d.rectangle((cx,cy-132,cx+132,cy),fill='#33495b')
            d.line((cx-138,cy,cx+138,cy),fill=GRID,width=1);d.line((cx,cy-138,cx,cy+138),fill=GRID,width=1)
            scene=self.cases[f'{name}_source{source}'];row=self.raw[engine,profile][scene['name']]
            for p in [p for p in row['paths'] if p['rx']==j]:
                pts=[point(q) for q in p['points']]
                d.line(pts,fill=color if 8 in p['interactions'] else '#648095',width=3 if 8 in p['interactions'] else 2)
            for label,q in [('TX',scene['tx']),('RX',scene['receivers'][j])]:
                a,b=point(q);d.ellipse((a-6,b-6,a+6,b+6),fill=WHITE if label=='TX' else color);text(a+9,b-12,label,17)
            d.ellipse((cx-4,cy-4,cx+4,cy+4),fill=color)
            text(x+24,252,'Top view • λ = 1 unit',20,MUTED)
            text(x+24,555,'53 measured receiver angles',17,MUTED)
            # Fixed scales shared by both engines and all chapters.
            gx,gy,gw,gh=x+345,287,365,184
            def chart(vals,lo,hi,y0,height,c):
                pts=[(gx+k/52*gw,y0+height*(1-np.clip((float(v)-lo)/(hi-lo),0,1))) for k,v in enumerate(vals)]
                d.line(pts,fill=c,width=3)
            text(gx,249,'Total field • dB re unit source',20,MUTED)
            for v in (-60,-40,-20):
                yy=gy+gh*(1-(v+70)/55);d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-32,yy-10,str(v),17,MUTED)
            chart(20*np.log10(abs(reference)),-70,-15,gy,gh,WHITE)
            chart(20*np.log10(abs(values)),-70,-15,gy,gh,color)
            xx=gx+j/52*gw;d.line((xx,gy,xx,gy+gh),fill=MUTED,width=1)
            for v,c in ((reference[j],WHITE),(values[j],color)):
                yy=gy+gh*(1-np.clip((20*np.log10(abs(v))+70)/55,0,1));d.ellipse((xx-4,yy-4,xx+4,yy+4),fill=c)
            text(gx,477,'5°',17,MUTED);text(gx+gw-38,477,'265°',17,MUTED)
            text(gx,520,'Phase error to Maxwell • degrees',20,MUTED)
            phase=np.rad2deg(np.angle(values/reference));py,ph=564,122
            for v in (-180,0,180):
                yy=py+ph*(1-(v+180)/360);d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-43,yy-10,str(v),17,MUTED)
            # Split wrapped phase jumps instead of drawing a fictitious crossing.
            for k in range(52):
                if abs(phase[k+1]-phase[k])<180:
                    d.line((gx+k/52*gw,py+ph*(1-(phase[k]+180)/360),gx+(k+1)/52*gw,py+ph*(1-(phase[k+1]+180)/360)),fill=color,width=3)
            d.line((xx,py,xx,py+ph),fill=MUTED)
            text(gx,711,f'Δ phase  {np.rad2deg(np.angle(u/ref)):+.2f}°',24,color,True)
            text(gx,749,f'Δ magnitude  {20*np.log10(abs(u/ref)):+.2f} dB',22)
            pc=(x+156,680);rad=64
            d.ellipse((pc[0]-rad,pc[1]-rad,pc[0]+rad,pc[1]+rad),outline=GRID,width=2)
            for v,c in ((ref,WHITE),(u,color)):
                a=np.angle(v);d.line((*pc,pc[0]+rad*np.cos(a),pc[1]-rad*np.sin(a)),fill=c,width=3)
            text(x+51,765,'Unit phasors: phase only',17,MUTED)
        d.line((40,845,1560,845),fill=GRID,width=3);d.line((40,845,40+1520*t/60,845),fill='#76ddb2',width=4)
        text(40,858,'White: Maxwell reference   •   Color: engine   •   Reciprocal cylindrical normalization',19,MUTED)
        text(1330,858,'7 NOV 2026',19,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');args=ap.parse_args();root=args.root.resolve()
    out=root/'outputs/differt-bridge/examples/diffraction_model_errors';out.mkdir(parents=True,exist_ok=True)
    frames=root/'work/diffraction-model-errors/frames';frames.mkdir(parents=True,exist_ok=True);renderer=Renderer(root)
    preview=[121,361,601,841,1081,1321];selection=preview if args.previews else range(1,1441)
    for frame in selection:
        im=renderer.render(frame);im.save(frames/f'frame_{frame:04d}.png',compress_level=1)
        if frame in preview:
            dest=out/'previews';dest.mkdir(exist_ok=True);im.save(dest/f'frame_{frame:04d}.png')
        if frame%240==1:print('FRAME',frame,flush=True)
    if not args.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440
        manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        (root/'work/diffraction-model-errors/frame_hashes.json').write_text(json.dumps(manifest,indent=2))
        record=dict(status='frames_ready',frames=1440,fps=24,width=W,height=H,duration_seconds=60,preview_frames=preview,frame_folder=str(frames.relative_to(root)).replace('\\','/'),analysis_sha256=hashlib.sha256((root/'work/diffraction-model-errors/analysis.json').read_bytes()).hexdigest(),chapters=[dict(start_seconds=c[0],title=c[1]) for c in CHAPTERS])
        (out/'animation_validation.json').write_text(json.dumps(record,indent=2))

if __name__=='__main__':main()
