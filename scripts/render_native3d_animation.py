"""Measured native 3D point-dipole comparison, no synthetic field interpolation."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_model_error_animation import F,B,BG,PANEL,TEXT,MUTED,GRID,WHITE,COLORS,read,z

CHAPTERS=[('Native 3D point-dipole fields','zz_s1_h8_p60','native'),('Existing reciprocal profile','zz_s1_h8_p60','reciprocal'),('Optional uniform 3D PEC correction','zz_s1_h8_p60','hertz'),('Crossed dipoles / skew propagation','zx_h8','hertz'),('Shadow boundary / total-field continuity','boundary_shadow_h8','hertz'),('Validated improvement and remaining limits','zz_s1_h8_p60','summary')]

class Renderer:
    def __init__(self,root):
        self.root=root;self.data=read(root/'work/native3d/final_analysis.json')
        self.native={(r['profile'],r['name']):r for r in self.data['comparisons']}
        self.updated={(r['profile'],r['name']):r for r in self.data['updated']}
        self.refined={r['name']:r for r in self.data['refinement']}
        self.cases={c['name']:c for c in read(root/'work/n3r/cases.json')['cases']}
        self.raw={}
        for e in COLORS:
            for mode,folder in [('native','n3r'),('reciprocal','n3f')]:self.raw[e,mode]={r['name']:r for r in read(root/f'work/{folder}/{e}-{mode}/{e}_float32.json')['cases']}
    def render(self,frame):
        t=(frame-1)/24;ch=min(int(t/10),5);title,name,mode=CHAPTERS[ch];c=self.cases[name];n=len(c['receivers']);j=min(n-1,int((t%10)/10*n))
        im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,color=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=color)
        text(40,24,'Native 3D diffraction against Maxwell',44,bold=True)
        text(40,83,'Point electric dipoles • Infinite PEC wedge reference • Actual Sionna and DiffeRT paths',24,MUTED)
        text(1280,34,f'{ch+1:02d} / 06 • {t:04.1f}s',24,MUTED)
        text(40,119,title,24,bold=True)
        for e,x in [('sionna',40),('differt',820)]:
            color=COLORS[e];updated=self.updated[e+'-reciprocal',name];base=z(updated['field']);ref=z(updated['reference'])
            if mode=='native':row=self.native[e+'-native',name];value=z([v['prediction'] for v in row['entries']]);m=row
            elif mode in ('hertz','summary'):m=self.refined[name];value=z(m['field'])
            else:m=updated;value=base
            d.rounded_rectangle((x,160,x+740,814),18,fill=PANEL)
            text(x+24,178,'Sionna RT' if e=='sionna' else 'DiffeRT',32,color,True)
            label={'native':'native ray field','reciprocal':'reciprocal ray field','hertz':'+ optional 3D PEC Hertz-UTD','summary':'native exports + separate 3D correction'}[mode]
            text(x+24,224,label,20,MUTED)
            text(x+389,178,f'{100*m["total_complex_rms"]:.3f}%',38,color,True)
            text(x+566,196,'complex RMS',19,MUTED)
            if mode=='summary':
                native=self.native[e+'-native',name]['total_complex_rms'];corrected=updated['total_complex_rms'];hertz=m['total_complex_rms']
                for yy,label,v,col in [(290,'Native',native,'#8293a3'),(356,'Reciprocal',corrected,'#9caeaa'),(422,'3D Hertz-UTD',hertz,color)]:
                    text(x+25,yy,label,22);d.rectangle((x+193,yy,x+193+v*750,yy+30),fill=col);text(x+208+v*750,yy,f'{100*v:.3f}%',22,col)
                text(x+25,505,'Fresh holdouts: 0.035–0.326% RMS',28,color,True)
                text(x+25,553,'Sionna opaque-slab NaNs fixed and validated.',22)
                text(x+25,601,'PEC wedge and edge-parallel source only.',22)
                text(x+25,644,'Dielectric 3D Maxwell accuracy is still unvalidated.',20,MUTED)
                text(x+25,688,'Extra obstacles are rejected by the optional mode.',20,MUTED)
                text(x+25,754,'Both runtimes and Blender workflow verified.',20,MUTED)
                continue
            # Oblique 3D projection of actual accepted native paths.
            project=lambda p:(x+167+24*(p[0]-.55*p[1]),535-24*(p[2]+.25*(p[0]+p[1])))
            for face in [[(0,0,0),(4,0,0),(4,0,9),(0,0,9)],[(0,0,0),(0,4,0),(0,4,9),(0,0,9)]]:d.polygon([project(p) for p in face],fill='#2a4051',outline=GRID)
            d.line([project((0,0,0)),project((0,0,9))],fill='#8aa0b1',width=3)
            for p in self.raw[e,'native' if mode=='native' else 'reciprocal'][name]['paths']:
                if p['rx']==j:d.line([project(q) for q in p['points']],fill=color if 8 in p['interactions'] else '#7c94a7',width=3)
            for lab,q,col in [('TX',c['tx'],WHITE),('RX',c['receivers'][j],color)]:
                px,py=project(q);d.ellipse((px-5,py-5,px+5,py+5),fill=col);text(px+8,py-10,lab,17,col)
            text(x+24,263,'3D geometry • λ = 1 m',20,MUTED)
            text(x+24,562,f'Height difference: {c["receivers"][j][2]-c["tx"][2]:g} λ',19,MUTED)
            text(x+24,594,f'RX port: {c["study"]["receiver_axis"]}-directed dipole',19,MUTED)
            text(x+24,626,f'RX angle: {c["study"]["angles"][j]:.6f}°',19,MUTED)
            gx,gw=x+359,348
            def chart(vals,low,high,y,h,col,width=3):
                d.line([(gx+i/(n-1)*gw,y+h*(1-np.clip((v-low)/(high-low),0,1))) for i,v in enumerate(vals)],fill=col,width=width)
            text(gx,263,'Coherent channel magnitude (dB)',19,MUTED)
            y,h=304,174
            for val in (-70,-50,-30):
                yy=y+h*(1-(val+85)/65);d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-34,yy-9,str(val),17,MUTED)
            if mode=='hertz':chart(20*np.log10(abs(base)),-85,-20,y,h,'#8293a3',2)
            chart(20*np.log10(abs(ref)),-85,-20,y,h,WHITE,4);chart(20*np.log10(abs(value)),-85,-20,y,h,color,2)
            xx=gx+j/(n-1)*gw;d.line((xx,y,xx,y+h),fill=MUTED)
            text(gx,487,'Ordered boundary samples' if ch==4 else '5°                 RX angle                 265°',17,MUTED)
            limit=2 if mode=='hertz' else 45;phase=np.rad2deg(np.angle(value/ref));y,h=562,126
            text(gx,524,f'Phase error • ±{limit}°'+(' zoom' if mode=='hertz' else ''),20,MUTED)
            for v in (-limit,0,limit):
                yy=y+h*(1-(v+limit)/(2*limit));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-32,yy-10,str(v),17,MUTED)
            chart(phase,-limit,limit,y,h,color);d.line((xx,y,xx,y+h),fill=MUTED)
            text(gx,713,f'Δ phase {phase[j]:+.4f}°',24,color,True)
            text(gx,753,f'{sum(abs(phase)>limit)}/{n} samples outside plot range',17,MUTED)
            text(x+24,689,'White: independent Maxwell',19)
            text(x+24,721,'Gray: reciprocal ray baseline',19,MUTED)
            text(x+24,753,'Colored: explicitly labelled mode',19,color)
        d.line((40,845,1560,845),fill=GRID,width=3);d.line((40,845,40+1520*t/60,845),fill='#76ddb2',width=4)
        text(40,860,'3D PEC correction is shared by both workflows; it does not turn dielectric UTD into an exact Maxwell solver.',19,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');a=ap.parse_args();root=a.root.resolve();out=root/'outputs/differt-bridge/examples/native3d_diffraction';out.mkdir(parents=True,exist_ok=True)
    frames=root/'work/native3d/frames';frames.mkdir(exist_ok=True);r=Renderer(root);previews=[121,361,601,841,1081,1321]
    for f in previews if a.previews else range(1,1441):
        im=r.render(f);im.save(frames/f'frame_{f:04d}.png',compress_level=1)
        if f in previews:(out/'previews').mkdir(exist_ok=True);im.save(out/'previews'/f'frame_{f:04d}.png')
        if f%240==1:print('FRAME',f,flush=True)
    if not a.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440
        (root/'work/native3d/frame_hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
        meta=dict(status='frames_ready',frames=1440,fps=24,width=1600,height=900,duration_seconds=60,preview_frames=previews,frame_folder=frames.relative_to(root).as_posix(),analysis_sha256=hashlib.sha256((root/'work/native3d/final_analysis.json').read_bytes()).hexdigest(),video_name='Sionna_vs_DiffeRT_Native3D.mp4',timeline_name='Native3D_Comparison.blend',chapters=[dict(start_seconds=i*10,title=c[0]) for i,c in enumerate(CHAPTERS)])
        (out/'animation_validation.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':main()
