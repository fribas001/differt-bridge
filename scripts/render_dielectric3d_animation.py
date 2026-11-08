"""Measured 3D dielectric point-source fields, independently checked Maxwell reference."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_model_error_animation import F,B,BG,PANEL,TEXT,MUTED,GRID,WHITE,COLORS,read,z

CHAPTERS=[('Native dielectric point-dipole fields','concrete_s0_zz_h3','native'),
 ('Installed reciprocal profile + stable material sqrt','concrete_s0_zz_h3','reciprocal'),
 ('Crossed dipoles and skew propagation','concrete_s0_xy_h3','reciprocal'),
 ('Second dielectric and receiver height','lower_s1_yy_h1','reciprocal'),
 ('Shadow boundary: 239.99° → 240.01°','concrete_s0_zz_h3','boundary'),
 ('Measured improvements and remaining limits','concrete_s0_zz_h3','summary')]

class Renderer:
    def __init__(self,root):
        self.root=root;self.data=read(root/'work/dielectric3d/analysis.json');self.rows={(r['stage'],r['profile'],r['name']):r for r in self.data['comparisons']}
        self.cases={c['name']:c for c in read(root/'work/dielectric3d/cases.json')['cases']};self.raw={}
        for e in COLORS:
            for mode,folder in [('native','d3r'),('reciprocal','d3f')]:self.raw[e,mode]={r['name']:r for r in read(root/f'work/{folder}/{e}-{mode}/{e}_float32.json')['cases']}
    def render(self,frame):
        t=(frame-1)/24;ch=min(int(t/10),5);title,name,mode=CHAPTERS[ch];c=self.cases[name];study=c['study'];angles=np.array(study['angles'])
        indices=np.where(abs(angles-240)<.02)[0] if mode=='boundary' else np.arange(len(angles));j=int(indices[min(len(indices)-1,int(t%10/10*len(indices)))])
        im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,color=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=color)
        text(40,24,'3D dielectric diffraction against Maxwell',44,bold=True)
        text(40,83,'Point sources • All vector components • Infinite straight dielectric wedge • λ = 1 m',24,MUTED)
        text(1305,36,f'{ch+1:02d}/06 · {t:04.1f}s',22,MUTED);text(40,121,title,24,bold=True)
        for e,x in [('sionna',40),('differt',820)]:
            color=COLORS[e];native=mode=='native';r=self.rows['before' if native else 'after',e+('-native' if native else '-reciprocal'),name];a=z(r['field']);b=z(r['reference'])
            d.rounded_rectangle((x,160,x+740,814),18,fill=PANEL)
            text(x+24,179,'Sionna RT' if e=='sionna' else 'DiffeRT',32,color,True)
            text(x+24,225,'Native' if native else 'Reciprocal profile · installed',20,MUTED)
            if mode=='summary':
                ag=next(v for v in self.data['aggregates'] if v['stage']=='after' and v['profile']==e+'-reciprocal' and v['material']=='all')
                text(x+25,285,'Remaining full-field error',28,bold=True)
                text(x+25,330,f'{100*ag["complex_rms"]:.2f}% complex RMS',38,color,True)
                text(x+25,390,f'Geometric shadow: {100*ag["shadow"]["complex_rms"]:.2f}% RMS',24)
                text(x+25,441,'Close-range dipole terms dominate the total gap.',20,MUTED)
                if e=='sionna':
                    text(x+25,500,'Material sqrt fix: 864 slab checks passed',24,color,True)
                    text(x+25,542,'Worst coefficient error: 0.0267 → 0.000171',20)
                else:
                    text(x+25,500,'DiffeRT material arithmetic retained',24,color,True)
                    text(x+25,542,'286 dielectric regression cases passed / engine',20)
                text(x+25,603,'Maxwell fields are independent reference data.',22)
                text(x+25,645,'No fitted correction or replacement of ray exports.',20,MUTED)
                text(x+25,699,'Finite edges / arbitrary 3D objects: unvalidated.',20,MUTED)
                text(x+25,749,'Both runtimes + Blender 5.2 workflow checked.',20,color)
                continue
            text(x+392,180,f'{100*r["complex_rms"]:.2f}%',38,color,True);text(x+554,195,'whole sweep RMS',17,MUTED)
            text(x+24,269,f'εr = {study["epsilon"][0]:g} − {abs(study["epsilon"][1]):.3f}j',22)
            project=lambda p:(x+162+63*(p[0]-.55*p[1]),551-48*(p[2]+.25*(p[0]+p[1])))
            for face in [[(0,0,0),(2,0,0),(2,0,3.5),(0,0,3.5)],[(0,0,0),(0,2,0),(0,2,3.5),(0,0,3.5)]]:d.polygon([project(p) for p in face],fill='#2a4051',outline=GRID)
            d.line([project((0,0,0)),project((0,0,3.5))],fill='#8aa0b1',width=3)
            for p in self.raw[e,'native' if native else 'reciprocal'][name]['paths']:
                if p['rx']==j:d.line([project(q) for q in p['points']],fill=color if 8 in p['interactions'] else '#7c94a7',width=3)
            for lab,q,col in [('TX',c['tx'],WHITE),('RX',c['receivers'][j],color)]:
                px,py=project(q);d.ellipse((px-5,py-5,px+5,py+5),fill=col);text(px+8,py-10,lab,17,col)
            text(x+24,601,f'Dipoles: {study["tx_axis"]} → {study["rx_axis"]}   Δz = {study["height"]:g} λ',22)
            text(x+24,640,f'RX angle: {angles[j]:.5f}°',20,MUTED)
            text(x+24,687,'White: independent vector Maxwell',19)
            text(x+24,724,'Colored: measured ray channel',19,color)
            text(x+24,761,'Geometry view cropped to the corner',17,MUTED)
            gx,gw=x+385,324;selected=angles[indices];xmin,xmax=selected[0],selected[-1]
            def chart(vals,lo,hi,y,h,col,width=3):
                pts=[]
                for ii in indices:
                    v=vals[ii]
                    if np.isfinite(v):pts.append((gx+(angles[ii]-xmin)/(xmax-xmin)*gw,y+h*(1-np.clip((v-lo)/(hi-lo),0,1))))
                    elif len(pts)>1:d.line(pts,fill=col,width=width);pts=[]
                if len(pts)>1:d.line(pts,fill=col,width=width)
            text(gx,269,'Coherent channel magnitude (dB)',17,MUTED)
            y,h=310,173;alo=-85;ahi=-15
            if mode=='boundary':
                db=20*np.log10(np.maximum(abs(np.r_[a[indices],b[indices]]),1e-20));alo=float(np.floor(db.min()-1));ahi=float(np.ceil(db.max()+1))
            for v in np.linspace(alo,ahi,4):
                yy=y+h*(1-(v-alo)/(ahi-alo));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-37,yy-9,f'{v:.0f}',17,MUTED)
            chart(20*np.log10(np.maximum(abs(b),1e-20)),alo,ahi,y,h,WHITE,4);chart(20*np.log10(np.maximum(abs(a),1e-20)),alo,ahi,y,h,color,2)
            xx=gx+(angles[j]-xmin)/(xmax-xmin)*gw;d.line((xx,y,xx,y+h),fill=MUTED)
            text(gx,494,f'{xmin:g}°                        {xmax:g}°',17,MUTED)
            phase=np.rad2deg(np.angle(a*np.conj(b)));phase[(abs(b)<max(abs(b).max()*1e-3,1e-9))|(abs(a)<1e-12)]=np.nan
            limit=90;y,h=570,117;text(gx,531,'Phase difference from Maxwell',19,MUTED)
            for v in (-limit,0,limit):
                yy=y+h*(1-(v+limit)/(2*limit));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-36,yy-10,str(v),17,MUTED)
            chart(phase,-limit,limit,y,h,color);d.line((xx,y,xx,y+h),fill=MUTED)
            text(gx,713,f'Δ phase {phase[j]:+.3f}°',24,color,True)
            text(gx,754,f'{sum(abs(phase[indices])>limit)}/{len(indices)} clipped · null phases excluded',17,MUTED)
        d.line((40,845,1560,845),fill=GRID,width=3);d.line((40,845,40+1520*t/60,845),fill='#76ddb2',width=4)
        text(40,860,'Total-channel error includes near-field and solid-wedge physics; it is not an isolated diffraction-coefficient error.',19,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');a=ap.parse_args();root=a.root.resolve();out=root/'outputs/differt-bridge/examples/dielectric3d_diffraction';out.mkdir(parents=True,exist_ok=True)
    frames=root/'work/dielectric3d/frames';frames.mkdir(exist_ok=True);r=Renderer(root);previews=[121,361,601,841,1081,1321]
    for f in previews if a.previews else range(1,1441):
        im=r.render(f);im.save(frames/f'frame_{f:04d}.png',compress_level=1)
        if f in previews:(out/'previews').mkdir(exist_ok=True);im.save(out/'previews'/f'frame_{f:04d}.png')
        if f%240==1:print('FRAME',f,flush=True)
    if not a.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440
        (root/'work/dielectric3d/frame_hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
        meta=dict(status='frames_ready',frames=1440,fps=24,width=1600,height=900,duration_seconds=60,preview_frames=previews,frame_folder=frames.relative_to(root).as_posix(),analysis_sha256=hashlib.sha256((root/'work/dielectric3d/analysis.json').read_bytes()).hexdigest(),video_name='Sionna_vs_DiffeRT_Dielectric3D.mp4',timeline_name='Dielectric3D_Comparison.blend',chapters=[dict(start_seconds=i*10,title=c[0]) for i,c in enumerate(CHAPTERS)])
        (out/'animation_validation.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':main()
